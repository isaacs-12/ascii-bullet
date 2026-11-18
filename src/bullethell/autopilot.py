"""A greedy dodging bot. Powers `start demo`, balance tests and screenshots."""

from __future__ import annotations

import math

from src.bullethell.engine import InputState, World

_MOVES = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]


def autopilot(world: World, lookahead: float = 0.35) -> InputState:
    """Pick the move whose predicted position is furthest from danger."""
    p = world.player
    pc = world.pc
    best, best_cost = InputState(), math.inf
    nearby = [b for b in world.bullets if abs(b.x - p.x) < 22 and abs(b.y - p.y) < 22]
    for focus in (False, True):
        speed = pc["focus_speed"] if focus else pc["speed"]
        for dx, dy in _MOVES:
            norm = math.hypot(dx, dy) or 1.0
            cost = 0.0
            for frac in (0.06, 0.4, 1.0):
                t = lookahead * frac
                px = min(world.width - 1.5, max(1.5, p.x + dx / norm * speed * t))
                py = min(world.height - 2, max(4, p.y + dy / norm * speed * t))
                for b in nearby:
                    bx, by = b.x + b.vx * t, b.y + b.vy * t
                    d = math.hypot(bx - px, by - py) - b.radius - pc["hitbox"]
                    if d < 0.4:
                        cost += 1000.0
                    elif d < 8:
                        cost += 1.0 / (d * d)
            # Prefer the lower-middle of the arena: room to dodge in every direction.
            cost += 0.002 * ((px - world.width / 2) ** 2) + 0.004 * ((py - world.height * 0.78) ** 2)
            if cost < best_cost:
                best_cost, best = cost, InputState(dx, dy, focus)
    if best_cost >= 1000 and p.bombs > 0 and world.bomb_time <= 0:
        best.bomb = True
    return best
