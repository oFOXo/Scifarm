from pathlib import Path
from scifarm.sim import GameSim, Machine


def test_build_solar_consumes_materials():
    sim = GameSim(seed=1)
    sim.resources.materials = 20
    sim.world[sim.player[1]][sim.player[0]] = "empty"
    reward = sim.apply_action("build_solar")
    assert reward > 0
    assert sim.resources.materials == 12
    assert any(m.name == "solar" for m in sim.machines)


def test_recycler_converts_waste_to_materials():
    sim = GameSim(seed=1)
    sim.resources.energy = 10
    sim.resources.waste = 2
    sim.resources.materials = 0
    sim.machines.append(Machine("recycler", 0, 0, "materials", 2, 1))
    sim.run_machines()
    assert sim.resources.waste == 1
    assert sim.resources.materials == 2


def test_save_load_roundtrip(tmp_path: Path):
    save = tmp_path / "save.json"
    sim = GameSim(seed=1, save_file=save)
    sim.day = 7
    sim.resources.energy = 77
    sim.save_game()

    loaded = GameSim(seed=2, save_file=save)
    loaded.load_game()
    assert loaded.day == 7
    assert loaded.resources.energy == 77
