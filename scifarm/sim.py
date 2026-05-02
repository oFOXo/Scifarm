from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

WORLD_W = 32
WORLD_H = 22


@dataclass
class ResourceState:
    energy: int = 40
    food: int = 35
    materials: int = 25
    water: int = 25
    waste: int = 0


@dataclass
class Machine:
    name: str
    x: int
    y: int
    output: str
    amount: int
    upkeep_energy: int


@dataclass
class FeatureGene:
    name: str
    probability: float
    color: str
    effect: str


@dataclass
class EvoGenome:
    mutation_rate: float = 0.15
    max_features: int = 12
    features: list[FeatureGene] = field(default_factory=list)

    def seed(self) -> None:
        if self.features:
            return
        self.features = [
            FeatureGene("solar_grid", 0.12, "gold", "energy"),
            FeatureGene("hydro_bed", 0.11, "lightgreen", "food"),
            FeatureGene("recycler", 0.10, "silver", "materials"),
        ]

    def mutate(self, rng: random.Random) -> FeatureGene | None:
        if rng.random() > self.mutation_rate or len(self.features) >= self.max_features:
            return None
        gene = FeatureGene(
            name=f"{rng.choice(['bio', 'aero', 'quantum', 'myco'])}_{rng.choice(['forge', 'dock', 'farm', 'spire'])}",
            probability=rng.uniform(0.05, 0.15),
            color=rng.choice(["orange", "cyan", "violet", "pink", "khaki"]),
            effect=rng.choice(["energy", "food", "materials", "water"]),
        )
        self.features.append(gene)
        return gene


class SimpleRLBrain:
    ACTIONS = ["farm", "mine", "build_solar", "build_recycler", "explore"]

    def __init__(self) -> None:
        self.q: dict[tuple[int, int, int, int], dict[str, float]] = {}
        self.alpha = 0.25
        self.gamma = 0.92
        self.epsilon = 0.20

    def state_key(self, r: ResourceState) -> tuple[int, int, int, int]:
        return (r.energy // 10, r.food // 10, r.materials // 10, r.water // 10)

    def pick_action(self, state: tuple[int, int, int, int], rng: random.Random) -> str:
        self.q.setdefault(state, {a: 0.0 for a in self.ACTIONS})
        if rng.random() < self.epsilon:
            return rng.choice(self.ACTIONS)
        return max(self.q[state], key=self.q[state].get)

    def learn(self, state, action: str, reward: float, next_state) -> None:
        self.q.setdefault(state, {a: 0.0 for a in self.ACTIONS})
        self.q.setdefault(next_state, {a: 0.0 for a in self.ACTIONS})
        self.q[state][action] += self.alpha * (
            reward + self.gamma * max(self.q[next_state].values()) - self.q[state][action]
        )


class GameSim:
    def __init__(self, seed: int = 42, save_file: Path = Path("savegame.json")) -> None:
        self.rng = random.Random(seed)
        self.day = 1
        self.player = [WORLD_W // 2, WORLD_H // 2]
        self.resources = ResourceState()
        self.machines: list[Machine] = []
        self.brain = SimpleRLBrain()
        self.genome = EvoGenome()
        self.genome.seed()
        self.save_file = save_file
        self.world = [["empty" for _ in range(WORLD_W)] for _ in range(WORLD_H)]
        self.decorate_world()

    def decorate_world(self) -> None:
        for y, row in enumerate(self.world):
            for x in range(len(row)):
                roll = self.rng.random()
                row[x] = (
                    "crop"
                    if roll < 0.12
                    else "scrap"
                    if roll < 0.22
                    else "water"
                    if roll < 0.28
                    else "empty"
                )

    def move(self, dx: int, dy: int) -> None:
        self.player[0] = max(0, min(WORLD_W - 1, self.player[0] + dx))
        self.player[1] = max(0, min(WORLD_H - 1, self.player[1] + dy))
        self.resources.energy = max(0, self.resources.energy - 1)

    def save_game(self) -> None:
        data = {
            "day": self.day,
            "player": self.player,
            "resources": asdict(self.resources),
            "machines": [asdict(m) for m in self.machines],
            "features": [asdict(f) for f in self.genome.features],
            "world": self.world,
        }
        self.save_file.write_text(json.dumps(data))

    def load_game(self) -> bool:
        if not self.save_file.exists():
            return False

        try:
            data = json.loads(self.save_file.read_text())
        except json.JSONDecodeError:
            return False

        self.day = int(data["day"])
        self.player = list(data["player"])
        self.resources = ResourceState(**data["resources"])
        self.machines = [Machine(**m) for m in data["machines"]]
        self.genome.features = [FeatureGene(**f) for f in data["features"]]
        self.world = data["world"]
        return True

    def apply_action(self, action: str) -> float:
        r = self.resources
        x, y = self.player
        tile = self.world[y][x]
        reward = -0.1

        if action == "farm" and tile == "crop":
            r.food += self.rng.randint(3, 7)
            r.water = max(0, r.water - 1)
            self.world[y][x] = "empty"
            reward += 2.2
        elif action == "mine" and tile == "scrap":
            r.materials += self.rng.randint(2, 5)
            r.waste += 1
            self.world[y][x] = "empty"
            reward += 1.8
        elif action == "build_solar" and r.materials >= 8:
            r.materials -= 8
            self.world[y][x] = "solar"
            self.machines.append(Machine("solar", x, y, "energy", 3, 0))
            reward += 3.5
        elif action == "build_recycler" and r.materials >= 10:
            r.materials -= 10
            self.world[y][x] = "recycler"
            self.machines.append(Machine("recycler", x, y, "materials", 2, 1))
            reward += 3.2
        elif action == "explore":
            self.move(self.rng.randint(-1, 1), self.rng.randint(-1, 1))
            reward += 0.7

        return reward

    def run_machines(self) -> None:
        energy = self.resources.energy
        materials_gain = 0
        waste_reduced = 0

        for machine in self.machines:
            if energy < machine.upkeep_energy:
                continue
            energy -= machine.upkeep_energy
            if machine.output == "energy":
                energy += machine.amount
            elif machine.output == "materials" and self.resources.waste > waste_reduced:
                waste_reduced += 1
                materials_gain += machine.amount

        self.resources.energy = energy
        self.resources.waste = max(0, self.resources.waste - waste_reduced)
        self.resources.materials += materials_gain

    def strategic_rollout_bonus(self) -> float:
        r = self.resources
        score = (r.energy + r.food + r.materials + r.water) / 80
        scarcity = 0.6 if min(r.energy, r.food, r.water) < 8 else 0
        waste_penalty = min(0.8, r.waste * 0.08)
        return max(-0.5, min(1.5, score - scarcity - waste_penalty))

    def tick(self) -> None:
        self.day += 1
        self.resources.food = max(0, self.resources.food - 1)
        self.resources.water = max(0, self.resources.water - 1)
        if self.resources.food == 0 or self.resources.water == 0:
            self.resources.energy = max(0, self.resources.energy - 2)

        self.run_machines()
        state = self.brain.state_key(self.resources)
        action = self.brain.pick_action(state, self.rng)
        reward = self.apply_action(action) + 0.3 * self.strategic_rollout_bonus()
        next_state = self.brain.state_key(self.resources)
        self.brain.learn(state, action, reward, next_state)
