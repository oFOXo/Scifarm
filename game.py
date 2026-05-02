import time
import turtle
from scifarm.sim import GameSim, WORLD_H, WORLD_W

TILE = 20

class SolarpunkGameUI:
    def __init__(self) -> None:
        self.sim = GameSim(seed=42)
        self.screen = turtle.Screen(); self.screen.setup(width=980, height=740); self.screen.bgcolor("#091625"); self.screen.title("Solarpunk Cyberpunk Factory Survival - v3"); self.screen.tracer(0)
        self.pen = turtle.Turtle(visible=False); self.pen.penup(); self.pen.speed(0)
        self.screen.listen(); self.screen.onkeypress(lambda: self.sim.move(0,1), "w"); self.screen.onkeypress(lambda: self.sim.move(0,-1), "s"); self.screen.onkeypress(lambda: self.sim.move(-1,0), "a"); self.screen.onkeypress(lambda: self.sim.move(1,0), "d"); self.screen.onkeypress(self.sim.save_game, "p"); self.screen.onkeypress(self.sim.load_game, "l")

    def color_for(self, tile: str) -> str:
        return {"empty":"#122246","crop":"#42d96b","scrap":"#8c95a3","water":"#3ea2ff","solar":"#ffd343","recycler":"#d5d9df"}.get(tile, "white")

    def draw_rect(self, x: int, y: int, color: str) -> None:
        px = -WORLD_W*TILE//2 + x*TILE; py = -WORLD_H*TILE//2 + y*TILE
        self.pen.goto(px, py); self.pen.fillcolor(color); self.pen.begin_fill()
        for _ in range(4): self.pen.forward(TILE); self.pen.left(90)
        self.pen.end_fill()

    def draw(self) -> None:
        self.pen.clear()
        for y in range(WORLD_H):
            for x in range(WORLD_W):
                self.draw_rect(x, y, self.color_for(self.sim.world[y][x]))
        self.draw_rect(self.sim.player[0], self.sim.player[1], "#24d4ff")
        r = self.sim.resources
        self.pen.goto(-470, 325); self.pen.color("white")
        self.pen.write(f"Day {self.sim.day} | E:{r.energy} F:{r.food} M:{r.materials} W:{r.water} Waste:{r.waste} Machines:{len(self.sim.machines)}", font=("Courier", 12, "bold"))
        self.screen.update()

    def run(self) -> None:
        while self.sim.resources.energy > 0:
            self.sim.tick(); self.draw(); time.sleep(0.12)
        self.screen.mainloop()

if __name__ == "__main__":
    SolarpunkGameUI().run()
