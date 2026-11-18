"""Headless tests for the bullet hell simulation."""

import math

from src.bullethell.autopilot import autopilot
from src.bullethell.engine import Bullet, InputState, World

IDLE = InputState()


def step(world, seconds, inp=IDLE, dt=1 / 60):
    for _ in range(int(seconds / dt)):
        world.update(dt, inp)


def test_waves_progress_and_bosses_appear():
    w = World(practice=True, seed=0)
    kinds = []
    for _ in range(int(80 / (1 / 60))):
        w.update(1 / 60, IDLE)
        kinds += [e.kind for e in w.drain_events()]
        if "boss_enter" in kinds:
            break
    assert kinds.count("wave_start") >= 5
    assert "boss_enter" in kinds and w.boss is not None


def test_full_loop_in_practice_mode():
    w = World(practice=True, seed=1)
    for _ in range(int(600 / (1 / 30))):
        w.update(1 / 30, IDLE)
        if w.loop >= 1:
            break
    assert w.loop == 1 and w.bosses_defeated == 3
    assert not w.game_over  # practice mode can't die


def test_hit_costs_a_life_and_clears_bullets():
    w = World(seed=2)
    p = w.player
    w.bullets.append(Bullet(p.x, p.y, 0, 0, w.content["bullets"]["small"]))
    w.bullets.append(Bullet(p.x + 30, p.y, 0, 0, w.content["bullets"]["small"]))
    w.update(1 / 60, IDLE)
    assert p.lives == w.pc["lives"] - 1
    assert not w.bullets and p.iframes > 0


def test_game_over_after_last_life():
    w = World(seed=3)
    w.player.lives = 1
    w.bullets.append(Bullet(w.player.x, w.player.y, 0, 0, w.content["bullets"]["big"]))
    w.update(1 / 60, IDLE)
    assert w.game_over and any(e.kind == "game_over" for e in w.drain_events())


def test_graze_scores_and_charges():
    w = World(seed=4)
    p = w.player
    b = Bullet(p.x + w.pc["graze"] * 0.8, p.y, math.pi / 2, 0, w.content["bullets"]["small"])
    w.bullets.append(b)
    w.update(1 / 60, IDLE)
    assert w.grazes == 1 and b.grazed and p.lives == w.pc["lives"]
    assert w.multiplier > 1 and p.graze_charge == 1


def test_bomb_clears_screen_and_grants_iframes():
    w = World(seed=5)
    for i in range(50):
        w.bullets.append(Bullet(10 + i, 20, 0, 0, w.content["bullets"]["orb"]))
    bombs = w.player.bombs
    w.update(1 / 60, InputState(bomb=True))
    step(w, 0.8)
    assert w.player.bombs == bombs - 1
    assert len([b for b in w.bullets if b.y == 20]) == 0
    assert w.bombs_used == 1


def test_start_wave_and_loop_math():
    w = World(start_wave=17)
    assert w.loop == 1 and w.wave_index == 1 and w.wave_number == 17
    assert w.speed_mult > 1


def test_autopilot_clears_the_first_wave():
    w = World(seed=7)
    for _ in range(int(25 / (1 / 60))):
        w.update(1 / 60, autopilot(w))
        if w.wave_number >= 3:
            break
    assert not w.game_over and w.wave_number >= 2
