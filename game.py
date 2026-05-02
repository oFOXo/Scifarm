import random
import time
import turtle
from dataclasses import dataclass, field


TILE = 20
WORLD_W = 32
WORLD_H = 22


@dataclass
class FeatureGene:
    name: str
    probability: float
    color: str
    effect: str


@dataclass
class EvoGenome:
    mutation_rate: float = 0.18
    max_features: int = 8
    features: list[FeatureGene] = field(default_factory=list)

    def seed(self) -> None:
        if self.features:
            return
        self.features = [
            FeatureGene("solar_grid", 0.10, "gold", "energy"),
            FeatureGene("hydro_bed", 0.11, "lightgreen", "food"),
            FeatureGene("recycler", 0.10, "silver", "materials"),
            FeatureGene("drone_nest", 0.08, "violet", "automation"),
        ]

    def mutate(self) -> FeatureGene | None:
        if random.random() > self.mutation_rate or len(self.features) >= self.max_features:
            return None

        prefixes = ["bio", "quantum", "sun", "aero", "myco", "plasma"]
        suffixes = ["forge", "hab", "farm", "loom", "dock", "spire"]
        effects = ["energy", "food", "materials", "defense", "speed"]
        palette = ["orange", "cyan", "pink", "khaki", "turquoise", "salmon"]

        name = f"{random.choice(prefixes)}_{random.choice(suffixes)}"
        gene = FeatureGene(
            name=name,
            probability=random.uniform(0.04, 0.14),
            color=random.choice(palette),
            effect=random.choice(effects),
        )
        self.features.append(gene)
        return gene


class SimpleRLBrain:
    """Very small Q-learning loop to pick high-value actions."""

    ACTIONS = ["farm", "mine", "build", "explore"]

    def __init__(self) -> None:
        self.q: dict[tuple[int, int, int], dict[str, float]] = {}
        self.alpha = 0.35
        self.gamma = 0.90
        self.epsilon = 0.22

    def state_key(self, energy: int, food: int, materials: int) -> tuple[int, int, int]:
        return (energy // 10, food // 10, materials // 10)

    def pick_action(self, state: tuple[int, int, int]) -> str:
        self.q.setdefault(state, {a: 0.0 for a in self.ACTIONS})
        if random.random() < self.epsilon:
            return random.choice(self.ACTIONS)
        return max(self.q[state], key=self.q[state].get)

    def learn(
        self,
        state: tuple[int, int, int],
        action: str,
        reward: float,
        next_state: tuple[int, int, int],
    ) -> None:
        self.q.setdefault(state, {a: 0.0 for a in self.ACTIONS})
        self.q.setdefault(next_state, {a: 0.0 for a in self.ACTIONS})
        current = self.q[state][action]
        future = max(self.q[next_state].values())
        self.q[state][action] = current + self.alpha * (reward + self.gamma * future - current)


class SolarpunkGame:
    def __init__(self) -> None:
        self.screen = turtle.Screen()
        self.screen.setup(width=980, height=740)
        self.screen.bgcolor("#0a1024")
        self.screen.title("Solarpunk-Cyberpunk Farm Factory Survival")
        self.screen.tracer(0)

        self.pen = turtle.Turtle(visible=False)
        self.pen.penup()
        self.pen.speed(0)

        self.player = [WORLD_W // 2, WORLD_H // 2]
        self.energy = 30
        self.food = 30
        self.materials = 20
        self.day = 1

        self.brain = SimpleRLBrain()
        self.genome = EvoGenome()
        self.genome.seed()

        self.world = [["empty" for _ in range(WORLD_W)] for _ in range(WORLD_H)]
        self.decorate_world()
        self.bind_keys()

    def decorate_world(self) -> None:
        for y in range(WORLD_H):
            for x in range(WORLD_W):
                roll = random.random()
                if roll < 0.08:
                    self.world[y][x] = "scrap"
                elif roll < 0.20:
                    self.world[y][x] = "crop"
                elif roll < 0.24:
                    self.world[y][x] = "factory"

    def bind_keys(self) -> None:
        self.screen.listen()
        self.screen.onkeypress(lambda: self.move(0, 1), "w")
        self.screen.onkeypress(lambda: self.move(0, -1), "s")
        self.screen.onkeypress(lambda: self.move(-1, 0), "a")
        self.screen.onkeypress(lambda: self.move(1, 0), "d")

    def move(self, dx: int, dy: int) -> None:
        self.player[0] = max(0, min(WORLD_W - 1, self.player[0] + dx))
        self.player[1] = max(0, min(WORLD_H - 1, self.player[1] + dy))
        self.energy = max(0, self.energy - 1)

    def tile_color(self, tile: str) -> str:
        return {
            "empty": "#122246",
            "scrap": "#7d889b",
            "crop": "#42d96b",
            "factory": "#f26f3d",
        }.get(tile, "white")

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

    def process_action(self, action: str) -> float:
        reward = 0.0
        x, y = self.player
        tile = self.world[y][x]

        if action == "farm":
            if tile == "crop":
                gain = random.randint(3, 7)
                self.food += gain
                reward += gain * 0.8
                self.world[y][x] = "empty"
            else:
                reward -= 0.8

        elif action == "mine":
            if tile == "scrap":
                gain = random.randint(2, 6)
                self.materials += gain
                reward += gain * 0.7
                self.world[y][x] = "empty"
            else:
                reward -= 0.7

        elif action == "build":
            if self.materials >= 8:
                self.materials -= 8
                self.energy += 5
                self.world[y][x] = "factory"
                reward += 3.0
            else:
                reward -= 0.6

        elif action == "explore":
            self.move(random.randint(-1, 1), random.randint(-1, 1))
            reward += 0.6

        return reward

    def recursive_ai_tick(self, depth: int = 3) -> float:
        """Recursive lookahead scoring to shape reward."""
        if depth <= 0:
            return 0.0
        baseline = (self.energy + self.food + self.materials) / 100
        branches = []
        for _ in range(3):
            branches.append(baseline + random.uniform(-0.6, 1.0) + 0.72 * self.recursive_ai_tick(depth - 1))
        return max(branches)

    def spawn_mutation_feature(self) -> None:
        new_gene = self.genome.mutate()
        if not new_gene:
            return

        for _ in range(15):
            x = random.randint(0, WORLD_W - 1)
            y = random.randint(0, WORLD_H - 1)
            if self.world[y][x] == "empty":
                self.world[y][x] = new_gene.name
                break

    def apply_feature_effects(self) -> None:
        x, y = self.player
        tile = self.world[y][x]
        for g in self.genome.features:
            if tile == g.name:
                if g.effect == "energy":
                    self.energy += 4
                elif g.effect == "food":
                    self.food += 4
                elif g.effect == "materials":
                    self.materials += 4
                elif g.effect == "speed":
                    self.energy += 2
                    self.food += 1
                elif g.effect == "defense":
                    self.energy += 1
                self.world[y][x] = "empty"

    def draw(self) -> None:
        self.pen.clear()
        for y in range(WORLD_H):
            for x in range(WORLD_W):
                tile = self.world[y][x]
                color = self.tile_color(tile)
                for gene in self.genome.features:
                    if tile == gene.name:
                        color = gene.color
                self.draw_rect(x, y, color)

        self.draw_rect(self.player[0], self.player[1], "#23b5ff")
        self.pen.goto(-470, 330)
        self.pen.color("white")
        self.pen.write(
            f"Day {self.day}  Energy:{self.energy}  Food:{self.food}  Materials:{self.materials}  Mutations:{len(self.genome.features)}",
            font=("Courier", 14, "bold"),
        )
        self.screen.update()

    def tick(self) -> None:
        self.day += 1
        self.food = max(0, self.food - 1)
        if self.food == 0:
            self.energy = max(0, self.energy - 2)

        state = self.brain.state_key(self.energy, self.food, self.materials)
        action = self.brain.pick_action(state)
        reward = self.process_action(action)
        reward += 0.25 * self.recursive_ai_tick(2)

        self.apply_feature_effects()
        if self.day % 8 == 0:
            self.spawn_mutation_feature()

        next_state = self.brain.state_key(self.energy, self.food, self.materials)
        self.brain.learn(state, action, reward, next_state)

    def run(self) -> None:
        while self.energy > 0:
            self.tick()
            self.draw()
            time.sleep(0.12)

        self.pen.goto(-120, 0)
        self.pen.color("#ff6b6b")
        self.pen.write("Simulation Ended - Out of energy", font=("Courier", 20, "bold"))
        self.screen.update()
        self.screen.mainloop()


if __name__ == "__main__":
    SolarpunkGame().run()
