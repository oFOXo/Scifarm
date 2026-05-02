import json
import random
import time
import turtle
from dataclasses import dataclass, asdict, field
from pathlib import Path

TILE = 20
WORLD_W = 32
WORLD_H = 22
SAVE_FILE = Path("savegame.json")


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

    def learn(self, s, a: str, reward: float, nxt) -> None:
        self.q.setdefault(s, {x: 0.0 for x in self.ACTIONS})
        self.q.setdefault(nxt, {x: 0.0 for x in self.ACTIONS})
        self.q[s][a] += self.alpha * (reward + self.gamma * max(self.q[nxt].values()) - self.q[s][a])


class SolarpunkGame:
    def __init__(self, seed: int = 42) -> None:
        self.rng = random.Random(seed)
        self.day = 1
        self.player = [WORLD_W // 2, WORLD_H // 2]
        self.resources = ResourceState()
        self.machines: list[Machine] = []
        self.log: list[str] = []

        self.brain = SimpleRLBrain()
        self.genome = EvoGenome()
        self.genome.seed()

        self.world = [["empty" for _ in range(WORLD_W)] for _ in range(WORLD_H)]
        self.decorate_world()

        self.screen = turtle.Screen()
        self.screen.setup(width=980, height=740)
        self.screen.bgcolor("#091625")
        self.screen.title("Solarpunk Cyberpunk Factory Survival - v2")
        self.screen.tracer(0)

        self.pen = turtle.Turtle(visible=False)
        self.pen.penup()
        self.pen.speed(0)

        self.bind_keys()

    def decorate_world(self) -> None:
        for y in range(WORLD_H):
            for x in range(WORLD_W):
                roll = self.rng.random()
                self.world[y][x] = "crop" if roll < 0.12 else "scrap" if roll < 0.22 else "water" if roll < 0.28 else "empty"

    def bind_keys(self) -> None:
        self.screen.listen()
        self.screen.onkeypress(lambda: self.move(0, 1), "w")
        self.screen.onkeypress(lambda: self.move(0, -1), "s")
        self.screen.onkeypress(lambda: self.move(-1, 0), "a")
        self.screen.onkeypress(lambda: self.move(1, 0), "d")
        self.screen.onkeypress(self.save_game, "p")
        self.screen.onkeypress(self.load_game, "l")

    def move(self, dx: int, dy: int) -> None:
        self.player[0] = max(0, min(WORLD_W - 1, self.player[0] + dx))
        self.player[1] = max(0, min(WORLD_H - 1, self.player[1] + dy))
        self.resources.energy = max(0, self.resources.energy - 1)

    def save_game(self) -> None:
        payload = {
            "day": self.day,
            "player": self.player,
            "resources": asdict(self.resources),
            "machines": [asdict(m) for m in self.machines],
            "features": [asdict(f) for f in self.genome.features],
            "world": self.world,
        }
        SAVE_FILE.write_text(json.dumps(payload))
        self.log_event("Saved game")

    def load_game(self) -> None:
        if not SAVE_FILE.exists():
            self.log_event("No save file")
            return
        data = json.loads(SAVE_FILE.read_text())
        self.day = data["day"]
        self.player = list(data["player"])
        self.resources = ResourceState(**data["resources"])
        self.machines = [Machine(**m) for m in data["machines"]]
        self.genome.features = [FeatureGene(**f) for f in data["features"]]
        self.world = data["world"]
        self.log_event("Loaded game")

    def log_event(self, msg: str) -> None:
        self.log.append(f"D{self.day}: {msg}")
        self.log = self.log[-6:]

    def color_for(self, tile: str) -> str:
        base = {"empty": "#122246", "crop": "#42d96b", "scrap": "#8c95a3", "water": "#3ea2ff", "solar": "#ffd343", "recycler": "#d5d9df"}
        for g in self.genome.features:
            if tile == g.name:
                return g.color
        return base.get(tile, "white")

    def draw_rect(self, x: int, y: int, color: str) -> None:
        px = -WORLD_W * TILE // 2 + x * TILE
        py = -WORLD_H * TILE // 2 + y * TILE
        self.pen.goto(px, py)
        self.pen.fillcolor(color)
        self.pen.begin_fill()
        for _ in range(4):
            self.pen.forward(TILE)
            self.pen.left(90)
        self.pen.end_fill()

    def apply_action(self, action: str) -> float:
        r = self.resources
        x, y = self.player
        tile = self.world[y][x]
        reward = -0.1

        if action == "farm":
            if tile == "crop":
                r.food += self.rng.randint(3, 7)
                r.water = max(0, r.water - 1)
                self.world[y][x] = "empty"
                reward += 2.2
        elif action == "mine":
            if tile == "scrap":
                r.materials += self.rng.randint(2, 5)
                r.waste += 1
                self.world[y][x] = "empty"
                reward += 1.8
        elif action == "build_solar" and r.materials >= 8:
            r.materials -= 8
            self.world[y][x] = "solar"
            self.machines.append(Machine("solar", x, y, "energy", 3, 0))
            self.log_event("Built solar")
            reward += 3.5
        elif action == "build_recycler" and r.materials >= 10:
            r.materials -= 10
            self.world[y][x] = "recycler"
            self.machines.append(Machine("recycler", x, y, "materials", 2, 1))
            self.log_event("Built recycler")
            reward += 3.2
        elif action == "explore":
            self.move(self.rng.randint(-1, 1), self.rng.randint(-1, 1))
            reward += 0.7

        return reward

    def run_machines(self) -> None:
        for m in self.machines:
            if self.resources.energy < m.upkeep_energy:
                continue
            self.resources.energy -= m.upkeep_energy
            if m.output == "energy":
                self.resources.energy += m.amount
            elif m.output == "materials":
                if self.resources.waste > 0:
                    self.resources.waste -= 1
                    self.resources.materials += m.amount

    def spawn_mutation(self) -> None:
        gene = self.genome.mutate(self.rng)
        if not gene:
            return
        for _ in range(20):
            x = self.rng.randint(0, WORLD_W - 1)
            y = self.rng.randint(0, WORLD_H - 1)
            if self.world[y][x] == "empty":
                self.world[y][x] = gene.name
                self.log_event(f"Mutation: {gene.name}")
                break

    def apply_feature_tile(self) -> None:
        tile = self.world[self.player[1]][self.player[0]]
        for g in self.genome.features:
            if tile == g.name:
                if g.effect == "energy":
                    self.resources.energy += 4
                elif g.effect == "food":
                    self.resources.food += 4
                elif g.effect == "materials":
                    self.resources.materials += 4
                elif g.effect == "water":
                    self.resources.water += 4
                self.world[self.player[1]][self.player[0]] = "empty"
                self.log_event(f"Activated {g.name}")

    def strategic_rollout_bonus(self) -> float:
        # deterministic bounded lookahead instead of unbounded random recursion
        score = (self.resources.energy + self.resources.food + self.resources.materials + self.resources.water) / 80
        scarcity_penalty = 0.6 if min(self.resources.energy, self.resources.food, self.resources.water) < 8 else 0
        waste_penalty = min(0.8, self.resources.waste * 0.08)
        return max(-0.5, min(1.5, score - scarcity_penalty - waste_penalty))

    def upkeep(self) -> None:
        self.resources.food = max(0, self.resources.food - 1)
        self.resources.water = max(0, self.resources.water - 1)
        if self.resources.food == 0 or self.resources.water == 0:
            self.resources.energy = max(0, self.resources.energy - 2)

    def draw(self) -> None:
        self.pen.clear()
        for y in range(WORLD_H):
            for x in range(WORLD_W):
                self.draw_rect(x, y, self.color_for(self.world[y][x]))
        self.draw_rect(self.player[0], self.player[1], "#24d4ff")

        self.pen.goto(-470, 325)
        self.pen.color("white")
        r = self.resources
        self.pen.write(f"Day {self.day} | E:{r.energy} F:{r.food} M:{r.materials} W:{r.water} Waste:{r.waste} Machines:{len(self.machines)} Mut:{len(self.genome.features)}", font=("Courier", 12, "bold"))

        y = 290
        for msg in self.log:
            self.pen.goto(-470, y)
            self.pen.write(msg, font=("Courier", 10, "normal"))
            y -= 16

        self.screen.update()

    def tick(self) -> None:
        self.day += 1
        self.upkeep()
        self.run_machines()

        s = self.brain.state_key(self.resources)
        action = self.brain.pick_action(s, self.rng)
        reward = self.apply_action(action)
        self.apply_feature_tile()

        if self.day % 7 == 0:
            self.spawn_mutation()

        reward += 0.3 * self.strategic_rollout_bonus()
        ns = self.brain.state_key(self.resources)
        self.brain.learn(s, action, reward, ns)

    def run(self) -> None:
        while self.resources.energy > 0:
            self.tick()
            self.draw()
            time.sleep(0.12)

        self.pen.goto(-160, 0)
        self.pen.color("#ff6b6b")
        self.pen.write("Simulation Ended - Energy depleted", font=("Courier", 18, "bold"))
        self.screen.update()
        self.screen.mainloop()


if __name__ == "__main__":
    SolarpunkGame(seed=42).run()
