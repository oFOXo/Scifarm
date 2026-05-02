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
        if not self.features:
            self.features = [
                FeatureGene("solar_grid", 0.12, "gold", "energy"),
                FeatureGene("hydro_bed", 0.11, "lightgreen", "food"),
                FeatureGene("recycler", 0.10, "silver", "materials"),
            ]

    def mutate(self, rng: random.Random) -> FeatureGene | None:
        if rng.random() > self.mutation_rate or len(self.features) >= self.max_features:
            return None
        gene = FeatureGene(
            name=f"{rng.choice(['bio','aero','quantum','myco'])}_{rng.choice(['forge','dock','farm','spire'])}",
            probability=rng.uniform(0.05, 0.15),
            color=rng.choice(["orange", "cyan", "violet", "pink", "khaki"]),
            effect=rng.choice(["energy", "food", "materials", "water"]),
        )
        self.features.append(gene)
        return gene

class SimpleRLBrain:
    ACTIONS = ["farm", "mine", "build_solar", "build_recycler", "explore"]
    def __init__(self) -> None:
        self.q: dict[tuple[int,int,int,int], dict[str,float]] = {}
        self.alpha = 0.25
        self.gamma = 0.92
        self.epsilon = 0.20
    def state_key(self, r: ResourceState) -> tuple[int,int,int,int]:
        return (r.energy//10, r.food//10, r.materials//10, r.water//10)
    def pick_action(self, s, rng: random.Random) -> str:
        self.q.setdefault(s, {a:0.0 for a in self.ACTIONS})
        return rng.choice(self.ACTIONS) if rng.random() < self.epsilon else max(self.q[s], key=self.q[s].get)
    def learn(self, s, a: str, reward: float, n) -> None:
        self.q.setdefault(s, {x:0.0 for x in self.ACTIONS}); self.q.setdefault(n, {x:0.0 for x in self.ACTIONS})
        self.q[s][a] += self.alpha * (reward + self.gamma * max(self.q[n].values()) - self.q[s][a])

class GameSim:
    def __init__(self, seed: int = 42, save_file: Path = Path("savegame.json")) -> None:
        self.rng = random.Random(seed)
        self.day = 1
        self.player = [WORLD_W // 2, WORLD_H // 2]
        self.resources = ResourceState()
        self.machines: list[Machine] = []
        self.log: list[str] = []
        self.brain = SimpleRLBrain()
        self.genome = EvoGenome(); self.genome.seed()
        self.save_file = save_file
        self.world = [["empty" for _ in range(WORLD_W)] for _ in range(WORLD_H)]
        self.decorate_world()

    def decorate_world(self) -> None:
        for y in range(WORLD_H):
            for x in range(WORLD_W):
                r = self.rng.random()
                self.world[y][x] = "crop" if r < 0.12 else "scrap" if r < 0.22 else "water" if r < 0.28 else "empty"

    def move(self, dx: int, dy: int) -> None:
        self.player[0] = max(0, min(WORLD_W - 1, self.player[0] + dx)); self.player[1] = max(0, min(WORLD_H - 1, self.player[1] + dy))
        self.resources.energy = max(0, self.resources.energy - 1)

    def save_game(self) -> None:
        self.save_file.write_text(json.dumps({"day": self.day, "player": self.player, "resources": asdict(self.resources), "machines": [asdict(m) for m in self.machines], "features": [asdict(f) for f in self.genome.features], "world": self.world}))

    def load_game(self) -> None:
        data = json.loads(self.save_file.read_text())
        self.day = data["day"]; self.player = list(data["player"]); self.resources = ResourceState(**data["resources"])
        self.machines = [Machine(**m) for m in data["machines"]]; self.genome.features = [FeatureGene(**f) for f in data["features"]]; self.world = data["world"]

    def apply_action(self, action: str) -> float:
        r = self.resources; x,y = self.player; tile = self.world[y][x]; reward = -0.1
        if action == "farm" and tile == "crop": r.food += self.rng.randint(3,7); r.water=max(0,r.water-1); self.world[y][x]="empty"; reward += 2.2
        elif action == "mine" and tile == "scrap": r.materials += self.rng.randint(2,5); r.waste += 1; self.world[y][x] = "empty"; reward += 1.8
        elif action == "build_solar" and r.materials >= 8: r.materials -= 8; self.world[y][x]="solar"; self.machines.append(Machine("solar",x,y,"energy",3,0)); reward += 3.5
        elif action == "build_recycler" and r.materials >= 10: r.materials -= 10; self.world[y][x]="recycler"; self.machines.append(Machine("recycler",x,y,"materials",2,1)); reward += 3.2
        elif action == "explore": self.move(self.rng.randint(-1,1), self.rng.randint(-1,1)); reward += 0.7
        return reward

    def run_machines(self) -> None:
        for m in self.machines:
            if self.resources.energy < m.upkeep_energy: continue
            self.resources.energy -= m.upkeep_energy
            if m.output == "energy": self.resources.energy += m.amount
            elif m.output == "materials" and self.resources.waste > 0: self.resources.waste -= 1; self.resources.materials += m.amount

    def strategic_rollout_bonus(self) -> float:
        score = (self.resources.energy + self.resources.food + self.resources.materials + self.resources.water) / 80
        scarcity = 0.6 if min(self.resources.energy, self.resources.food, self.resources.water) < 8 else 0
        return max(-0.5, min(1.5, score - scarcity - min(0.8, self.resources.waste * 0.08)))

    def tick(self) -> None:
        self.day += 1
        self.resources.food = max(0, self.resources.food - 1); self.resources.water = max(0, self.resources.water - 1)
        if self.resources.food == 0 or self.resources.water == 0: self.resources.energy = max(0, self.resources.energy - 2)
        self.run_machines()
        s = self.brain.state_key(self.resources); a = self.brain.pick_action(s, self.rng)
        reward = self.apply_action(a) + 0.3 * self.strategic_rollout_bonus(); n = self.brain.state_key(self.resources)
        self.brain.learn(s, a, reward, n)
