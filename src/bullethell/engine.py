"""
Bullet hell simulation. Pure Python, no pygame: the state feeds it input and
draws whatever it contains, and tests can run it headless.

Coordinates are isotropic "world units" (x right, y down). The renderer maps
them onto character cells, squashing y by the cell aspect ratio so rings look
round on screen. Times in the JSON are milliseconds; internally seconds.

Content (enemies, waves, bosses, bullet types, tuning) lives in
``src/data/waves.json``.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "waves.json"
TAU = math.tau


def load_content() -> dict:
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- entities

class Bullet:
    __slots__ = ("x", "y", "vx", "vy", "radius", "glyph", "color", "age", "turn", "accel",
                 "stop_after", "aim_after", "aim_speed", "grazed", "directional", "alive")

    def __init__(self, x, y, angle, speed, btype: dict, color=None, turn=0.0, accel=0.0,
                 stop_after=None, aim_after=None, aim_speed=0.0):
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(angle) * speed, math.sin(angle) * speed
        self.radius = btype["radius"]
        self.glyph = btype["glyph"]
        self.directional = btype.get("directional", False)
        self.color = tuple(color or btype["color"])
        self.age = 0.0
        self.turn = math.radians(turn)
        self.accel = accel
        self.stop_after = stop_after
        self.aim_after = aim_after
        self.aim_speed = aim_speed
        self.grazed = False
        self.alive = True

    def display_glyph(self) -> str:
        if not self.directional:
            return self.glyph
        ang = math.degrees(math.atan2(self.vy, self.vx)) % 180
        return "-" if ang < 22.5 or ang >= 157.5 else ("\\" if ang < 67.5 else ("|" if ang < 112.5 else "/"))


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    glyph: str
    color: tuple
    max_life: float = 0.0

    def __post_init__(self):
        self.max_life = self.max_life or self.life


@dataclass
class Popup:
    x: float
    y: float
    text: str
    color: tuple
    life: float = 0.9


@dataclass
class InputState:
    dx: float = 0.0
    dy: float = 0.0
    focus: bool = False
    bomb: bool = False


@dataclass
class Player:
    x: float
    y: float
    lives: int
    bombs: int
    iframes: float = 0.0
    focus: bool = False
    graze_charge: int = 0
    hits_this_phase: int = 0


class Emitter:
    """Fires one pattern from an owner (enemy or boss)."""

    def __init__(self, spec: dict, world: World, color, delay: float = 0.0):
        self.spec = spec
        self.world = world
        self.kind = spec["type"]
        rate_mul = world.rate_mult
        self.interval = max(0.05, spec.get("interval", 1000) / 1000.0 / rate_mul)
        self.timer = self.interval * 0.5 + delay + spec.get("offset", 0) / 1000.0
        self.angle = random.uniform(0, TAU) if self.kind in ("ring", "spiral", "flower") else 0.0
        self.btype = world.content["bullets"][spec.get("bullet", "small")]
        self.color = spec.get("color") or color  # None -> the bullet type's own colour
        self.telegraph_time = spec.get("telegraph", 0) / 1000.0
        self.charging = 0.0
        self.locked_angle = 0.0
        self.volleys = 0

    def speed(self, key: str = "speed", default: float = 18.0) -> float:
        return self.spec.get(key, default) * self.world.speed_mult

    def update(self, dt: float, ox: float, oy: float) -> bool:
        """Advance; returns True when a volley fired."""
        if self.charging > 0:
            self.charging -= dt
            if self.charging <= 0:
                self._fire(ox, oy, locked=True)
                return True
            return False
        self.timer -= dt
        if self.timer > 0:
            return False
        self.timer += self.interval
        if self.telegraph_time > 0:
            self.charging = self.telegraph_time
            self.locked_angle = self.world.angle_to_player(ox, oy)
            return False
        self._fire(ox, oy)
        return True

    def _bullet(self, x, y, angle, speed, **extra) -> None:
        s = self.spec
        self.world.spawn_bullet(Bullet(
            x, y, angle, speed, self.btype, self.color,
            turn=extra.get("turn", s.get("curve", 0.0)), accel=s.get("accel", 0.0),
            stop_after=(s["stop_after"] / 1000.0) if "stop_after" in s else None,
            aim_after=(s["aim_after"] / 1000.0) if "aim_after" in s else None,
            aim_speed=s.get("aim_speed", 0.0) * self.world.speed_mult,
        ))

    def _fire(self, ox: float, oy: float, locked: bool = False) -> None:
        s, w = self.spec, self.world
        self.volleys += 1
        k = self.kind
        if k == "aimed":
            base = self.locked_angle if locked else w.angle_to_player(ox, oy)
            count = s.get("count", 1)
            spread = math.radians(s.get("spread", 0))
            for i in range(count):
                off = 0.0 if count == 1 else -spread / 2 + spread * i / (count - 1)
                self._bullet(ox, oy, base + off, self.speed())
        elif k in ("ring", "flower"):
            count = s.get("count", 12)
            for i in range(count):
                self._bullet(ox, oy, self.angle + TAU * i / count, self.speed())
            self.angle += math.radians(s.get("rotate", 0))
        elif k == "spiral":
            arms = s.get("arms", 2)
            for i in range(arms):
                self._bullet(ox, oy, self.angle + TAU * i / arms, self.speed())
            self.angle += math.radians(s.get("spin", 90)) * self.interval
        elif k == "drop":
            count = s.get("count", 1)
            spread = math.radians(s.get("spread", 0))
            for i in range(count):
                off = 0.0 if count == 1 else -spread / 2 + spread * i / (count - 1)
                self._bullet(ox, oy + 1, math.pi / 2 + off, self.speed())
        elif k == "rain":
            for _ in range(s.get("count", 3)):
                self._bullet(random.uniform(1, w.width - 1), 0.5, math.pi / 2 + random.uniform(-0.25, 0.25),
                             self.speed() * random.uniform(0.8, 1.2))
        elif k == "random":
            for _ in range(s.get("count", 4)):
                self._bullet(ox, oy, random.uniform(0, TAU), self.speed() * random.uniform(0.7, 1.3))
        elif k == "wall":
            gap = s.get("gap", 14)
            gap_x = random.uniform(gap, w.width - gap)
            x = 1.0
            while x < w.width - 1:
                if abs(x - gap_x) > gap / 2:
                    self._bullet(x, oy + 2, math.pi / 2, self.speed())
                x += self.btype["radius"] * 2.6 + 0.6


class Enemy:
    def __init__(self, kind: str, spec: dict, world: World, x: float, y: float, target_x: float,
                 target_y: float, side: str | None = None):
        self.kind = kind
        self.spec = spec
        self.world = world
        self.art = spec["art"]
        self.color = tuple(spec["color"])
        self.x, self.y = x, y
        self.target_x, self.target_y = target_x, target_y
        self.move = spec.get("move", "hover")
        self.speed = spec.get("speed", 18)
        self.state = "enter"
        self.age = 0.0
        self.alive = True
        self.depleted = False
        self.direction = 1 if (side or ("left" if x < world.width / 2 else "right")) == "left" else -1
        self.ammo = max(1, round(spec.get("ammo", 6) * (1 + 0.15 * world.loop)))
        self.emitters = [Emitter(p, world, self.color, delay=random.uniform(0, 0.4)) for p in spec["patterns"]]
        self.flash = 0.0

    @property
    def width(self) -> int:
        return max(len(line) for line in self.art)

    def update(self, dt: float) -> None:
        self.age += dt
        self.flash = max(0.0, self.flash - dt)
        w = self.world
        if self.state == "exit":
            self.y -= 30 * dt
            if self.y < -6:
                self.alive = False
            return
        if self.move in ("weave", "cross"):
            self.x += self.direction * self.speed * dt
            if self.move == "weave":
                self.y = self.target_y + math.sin(self.age * 2.2) * 6
            else:
                self.y += (self.target_y - self.y) * min(1.0, dt * 3)
            if (self.direction > 0 and self.x > w.width + 6) or (self.direction < 0 and self.x < -6):
                self.alive = False
                return
            self.state = "active"
        else:
            if self.state == "enter":
                self.x += (self.target_x - self.x) * min(1.0, dt * 2.5)
                self.y += (self.target_y - self.y) * min(1.0, dt * 2.5)
                if abs(self.y - self.target_y) < 0.8:
                    self.state = "active"
            else:
                self.x = self.target_x + math.sin(self.age * 0.9) * 3
        if self.state == "active" and 0 <= self.x <= w.width:
            for em in self.emitters:
                if em.update(dt, self.x, self.y + 1):
                    self.ammo -= 1
                    self.flash = 0.08
            if self.ammo <= 0 or self.age > 16:
                self.depleted = self.ammo <= 0
                self.state = "exit"
                if self.depleted:
                    w.on_enemy_depleted(self)


class Boss:
    def __init__(self, key: str, spec: dict, world: World, index: int):
        self.key = key
        self.spec = spec
        self.world = world
        self.index = index
        self.name = spec["name"]
        self.subtitle = spec.get("subtitle", "")
        self.art = spec["art"]
        self.color = tuple(spec["color"])
        self.x, self.y = world.width / 2, -8.0
        self.phase_index = -1
        self.phase_time = 0.0
        self.t = 0.0
        self.entering = True
        self.emitters: list[Emitter] = []
        self.flash = 0.0
        self.teleport_timer = 0.0
        self.alive = True

    @property
    def phases(self) -> list:
        return self.spec["phases"]

    @property
    def phase(self) -> dict:
        return self.phases[max(0, self.phase_index)]

    def phase_fraction(self) -> float:
        if self.phase_index < 0:
            return 1.0
        return max(0.0, 1.0 - self.phase_time / self.phase["duration"])

    def start_phase(self, i: int) -> None:
        self.phase_index = i
        self.phase_time = 0.0
        self.emitters = [Emitter(p, self.world, None, delay=0.6) for p in self.phase["patterns"]]
        self.world.player.hits_this_phase = 0

    def update(self, dt: float) -> None:
        self.t += dt
        self.flash = max(0.0, self.flash - dt)
        w = self.world
        if self.entering:
            self.y += (16 - self.y) * min(1.0, dt * 1.8)
            if abs(self.y - 16) < 0.5:
                self.entering = False
                self.start_phase(0)
                w.emit("boss_phase", phase=self.phase["name"], index=0)
            return
        move = self.phase.get("move", "sway")
        cx = w.width / 2
        if move == "sway":
            self.x = cx + math.sin(self.t * 0.55) * w.width * 0.28
        elif move == "center":
            self.x += (cx - self.x) * min(1.0, dt * 2)
            self.y = 16 + math.sin(self.t * 1.3) * 1.5
        elif move == "teleport":
            self.teleport_timer -= dt
            if self.teleport_timer <= 0:
                self.teleport_timer = 3.0
                w.burst(self.x, self.y, self.color, 14, 18)
                self.x = random.uniform(w.width * 0.2, w.width * 0.8)
                w.burst(self.x, self.y, self.color, 14, 18)
        for em in self.emitters:
            if em.update(dt, self.x, self.y + 2) and em.interval >= 0.4:
                self.flash = 0.06  # flash on heavy volleys only; spirals would strobe
        self.phase_time += dt
        if self.phase_time >= self.phase["duration"]:
            w.on_boss_phase_cleared(self)


# ------------------------------------------------------------------- world

@dataclass
class Event:
    kind: str
    data: dict = field(default_factory=dict)


class World:
    def __init__(self, content: dict | None = None, start_wave: int = 1, practice: bool = False,
                 seed: int | None = None):
        if seed is not None:
            random.seed(seed)
        self.content = content or load_content()
        self.width = float(self.content["world"]["width"])
        self.height = float(self.content["world"]["height"])
        pc = self.content["player"]
        self.pc = pc
        self.player = Player(self.width / 2, self.height - 10, pc["lives"], pc["bombs"])
        self.practice = practice

        self.bullets: list[Bullet] = []
        self.enemies: list[Enemy] = []
        self.particles: list[Particle] = []
        self.popups: list[Popup] = []
        self.boss: Boss | None = None
        self.events: list[Event] = []

        n_waves = len(self.content["waves"])
        start_wave = max(1, start_wave)
        self.wave_number = start_wave  # absolute, 1-based
        self.loop = (start_wave - 1) // n_waves
        self.wave_index = (start_wave - 1) % n_waves
        self.phase = "intermission"  # intermission | wave | warning | boss | boss_clear | game_over
        self.phase_timer = 2.0
        self.spawn_queue: list[tuple[float, dict]] = []
        self.wave_time = 0.0

        self.score = 0
        self.multiplier = 1.0
        self.since_graze = 0.0
        self.grazes = 0
        self.bombs_used = 0
        self.bosses_defeated = 0
        self.enemies_depleted = 0
        self.time_alive = 0.0
        self.bomb_time = 0.0
        self.bomb_radius = 0.0
        self.time_scale = 1.0
        self.slowmo_timer = 0.0
        self.game_over = False
        self.closest_call = 999.0
        self._update_difficulty()
        self.emit("wave_start", wave=self.wave_number, loop=self.loop)

    # ------------------------------------------------------------ helpers
    def emit(self, kind: str, **data) -> None:
        self.events.append(Event(kind, data))

    def drain_events(self) -> list[Event]:
        events, self.events = self.events, []
        return events

    def _update_difficulty(self) -> None:
        ws, ls = self.content["wave_scaling"], self.content["loop_scaling"]
        self.speed_mult = 1 + ws["speed"] * self.wave_index + ls["speed"] * self.loop
        self.rate_mult = 1 + ws["rate"] * self.wave_index + ls["rate"] * self.loop

    def angle_to_player(self, x: float, y: float) -> float:
        return math.atan2(self.player.y - y, self.player.x - x)

    def spawn_bullet(self, bullet: Bullet) -> None:
        if len(self.bullets) < 1500:
            self.bullets.append(bullet)

    def add_score(self, points: float, x: float | None = None, y: float | None = None, color=(255, 255, 160)) -> None:
        pts = int(points)
        if pts <= 0:
            return
        self.score += pts
        if x is not None and y is not None:
            self.popups.append(Popup(x, y, f"+{pts:,}", color))

    def burst(self, x: float, y: float, color, count: int = 12, speed: float = 20, glyphs: str = "*+.") -> None:
        for _ in range(count):
            a = random.uniform(0, TAU)
            v = random.uniform(0.3, 1.0) * speed
            self.particles.append(Particle(x, y, math.cos(a) * v, math.sin(a) * v,
                                           random.uniform(0.3, 0.8), random.choice(glyphs), color))

    def cancel_bullets(self, score_each: int = 0) -> int:
        n = 0
        for b in self.bullets:
            if b.alive:
                n += 1
                if random.random() < 0.35:
                    self.particles.append(Particle(b.x, b.y, 0, -6, 0.5, "+", (255, 255, 180)))
        if score_each and n:
            self.add_score(n * score_each * self.multiplier, self.player.x, self.player.y - 6)
        self.bullets = []
        return n

    # --------------------------------------------------------- wave flow
    def _queue_wave(self) -> None:
        wave = self.content["waves"][self.wave_index]
        self.wave_time = 0.0
        if "boss" in wave:
            self.phase = "warning"
            self.phase_timer = 2.6
            self.emit("boss_warning", name=self.content["bosses"][wave["boss"]]["name"])
            return
        self.phase = "wave"
        self.spawn_queue = sorted(((s.get("delay", 0) / 1000.0, s) for s in wave["spawns"]), key=lambda t: t[0])
        extra = self.loop  # later loops add one more of the first group
        if extra:
            first = dict(self.spawn_queue[0][1])
            first["count"] = first.get("count", 1) + extra
            self.spawn_queue[0] = (self.spawn_queue[0][0], first)

    def _spawn_group(self, group: dict) -> None:
        kind = group["enemy"]
        spec = self.content["enemies"][kind]
        count = group.get("count", 1)
        formation = group.get("formation", "line")
        side = group.get("side")
        for i in range(count):
            frac = (i + 1) / (count + 1)
            tx = self.width * (0.1 + 0.8 * frac)
            ty = 12 + (abs(frac - 0.5) * 18 if formation == "v" else random.uniform(0, 6))
            if spec.get("move") in ("weave", "cross"):
                from_left = (side or ("left" if i % 2 == 0 else "right")) == "left"
                x = -4 - i * 8 if from_left else self.width + 4 + i * 8
                self.enemies.append(Enemy(kind, spec, self, x, ty, tx, ty, "left" if from_left else "right"))
            else:
                self.enemies.append(Enemy(kind, spec, self, tx, -4 - i * 2, tx, ty))

    def _next_wave(self) -> None:
        self.wave_number += 1
        self.wave_index += 1
        if self.wave_index >= len(self.content["waves"]):
            self.wave_index = 0
            self.loop += 1
            self.emit("loop", loop=self.loop)
        self._update_difficulty()
        self.phase = "intermission"
        self.phase_timer = 2.0
        self.emit("wave_start", wave=self.wave_number, loop=self.loop)

    def on_enemy_depleted(self, enemy: Enemy) -> None:
        self.enemies_depleted += 1
        self.add_score(150 * (1 + self.wave_index + 3 * self.loop), enemy.x, enemy.y, (160, 255, 160))
        self.emit("depleted", enemy=enemy.kind)

    def on_boss_phase_cleared(self, boss: Boss) -> None:
        idx = boss.phase_index
        captured = self.player.hits_this_phase == 0
        self.cancel_bullets(score_each=10)
        loop_factor = 1 + self.loop
        self.add_score(2000 * (idx + 1) * loop_factor, boss.x, boss.y + 4, (255, 220, 120))
        if captured:
            self.add_score(5000 * (idx + 1) * loop_factor, boss.x, boss.y + 6, (120, 255, 255))
        self.emit("boss_phase_cleared", index=idx, captured=captured, name=boss.phase["name"])
        if idx + 1 < len(boss.phases):
            boss.start_phase(idx + 1)
            self.emit("boss_phase", phase=boss.phase["name"], index=idx + 1)
        else:
            self.bosses_defeated += 1
            self.add_score(10000 * (boss.index + 1) * loop_factor, boss.x, boss.y, (255, 255, 255))
            for _ in range(4):
                self.burst(boss.x + random.uniform(-5, 5), boss.y + random.uniform(-3, 3), boss.color, 30, 40,
                           "*#@%+")
            self.boss = None
            self.phase = "boss_clear"
            self.phase_timer = 3.0
            self.slowmo_timer = 1.2
            self.emit("boss_defeated", name=boss.name, wave=self.wave_number)

    # ------------------------------------------------------------ update
    def update(self, dt: float, inp: InputState) -> None:
        if self.game_over:
            self._update_fx(dt)
            return
        if self.slowmo_timer > 0:
            self.slowmo_timer -= dt
            self.time_scale = 0.35
        else:
            self.time_scale = min(1.0, self.time_scale + dt * 2)
        sdt = dt * self.time_scale

        self.time_alive += dt
        self._update_player(dt, inp)
        self._update_flow(sdt)
        for e in self.enemies:
            e.update(sdt)
        self.enemies = [e for e in self.enemies if e.alive]
        if self.boss:
            self.boss.update(sdt)
        self._update_bullets(sdt)
        self._update_fx(dt)

        # Score trickles in for surviving; multiplier decays without grazes.
        self.add_score(10 * self.multiplier * dt)
        self.since_graze += dt
        if self.since_graze > 3 and self.multiplier > 1:
            self.multiplier = max(1.0, self.multiplier - 0.15 * dt)

    def _update_player(self, dt: float, inp: InputState) -> None:
        p, pc = self.player, self.pc
        p.focus = inp.focus
        speed = pc["focus_speed"] if inp.focus else pc["speed"]
        dx, dy = inp.dx, inp.dy
        mag = math.hypot(dx, dy)
        if mag > 1:
            dx, dy = dx / mag, dy / mag
        p.x = min(self.width - 1.5, max(1.5, p.x + dx * speed * dt))
        p.y = min(self.height - 2, max(4, p.y + dy * speed * dt))
        p.iframes = max(0.0, p.iframes - dt)

        if inp.bomb and p.bombs > 0 and self.bomb_time <= 0:
            p.bombs -= 1
            self.bombs_used += 1
            self.bomb_time = 1.2
            self.bomb_radius = 0.0
            p.iframes = max(p.iframes, 1.6)
            self.emit("bomb")
        if self.bomb_time > 0:
            self.bomb_time -= dt
            self.bomb_radius = (1.2 - self.bomb_time) / 0.6 * max(self.width, self.height)
            r2 = self.bomb_radius ** 2
            cleared = 0
            for b in self.bullets:
                if b.alive and (b.x - p.x) ** 2 + (b.y - p.y) ** 2 < r2:
                    b.alive = False
                    cleared += 1
                    if random.random() < 0.3:
                        self.particles.append(Particle(b.x, b.y, 0, -8, 0.5, "+", (255, 255, 200)))
            if cleared:
                self.add_score(cleared * 20 * self.multiplier)

    def _update_flow(self, dt: float) -> None:
        self.phase_timer -= dt
        if self.phase == "intermission" and self.phase_timer <= 0:
            self._queue_wave()
        elif self.phase == "wave":
            self.wave_time += dt
            while self.spawn_queue and self.spawn_queue[0][0] <= self.wave_time:
                self._spawn_group(self.spawn_queue.pop(0)[1])
            if not self.spawn_queue and not self.enemies:
                self.bullets = [b for b in self.bullets if b.alive]
                self._next_wave()
        elif self.phase == "warning" and self.phase_timer <= 0:
            key = self.content["waves"][self.wave_index]["boss"]
            boss_order = [w["boss"] for w in self.content["waves"] if "boss" in w]
            self.boss = Boss(key, self.content["bosses"][key], self, boss_order.index(key))
            self.phase = "boss"
            self.emit("boss_enter", name=self.boss.name)
        elif self.phase == "boss_clear" and self.phase_timer <= 0:
            self._next_wave()

    def _update_bullets(self, dt: float) -> None:
        p = self.player
        graze_r = self.pc["graze"]
        hit_r = self.pc["hitbox"]
        w, h = self.width, self.height
        hit = False
        for b in self.bullets:
            if not b.alive:
                continue
            b.age += dt
            if b.stop_after is not None and b.age >= b.stop_after:
                b.vx = b.vy = 0.0
                b.stop_after = None
            if b.aim_after is not None and b.age >= b.aim_after:
                ang = math.atan2(p.y - b.y, p.x - b.x)
                b.vx, b.vy = math.cos(ang) * b.aim_speed, math.sin(ang) * b.aim_speed
                b.aim_after = None
            if b.turn:
                c, s = math.cos(b.turn * dt), math.sin(b.turn * dt)
                b.vx, b.vy = b.vx * c - b.vy * s, b.vx * s + b.vy * c
            if b.accel:
                sp = math.hypot(b.vx, b.vy)
                if sp > 0:
                    k = max(0.0, sp + b.accel * dt) / sp
                    b.vx *= k
                    b.vy *= k
            b.x += b.vx * dt
            b.y += b.vy * dt
            if b.x < -4 or b.x > w + 4 or b.y < -6 or b.y > h + 4:
                b.alive = False
                continue
            dx, dy = b.x - p.x, b.y - p.y
            d2 = dx * dx + dy * dy
            lim = graze_r + b.radius
            if d2 < lim * lim:
                d = math.sqrt(d2)
                if d < hit_r + b.radius:
                    if p.iframes <= 0:
                        hit = True
                        b.alive = False
                elif not b.grazed:
                    b.grazed = True
                    self._graze(b, d)
        self.bullets = [b for b in self.bullets if b.alive]
        if hit:
            self._on_hit()

    def _graze(self, b: Bullet, distance: float) -> None:
        p = self.player
        self.grazes += 1
        self.since_graze = 0.0
        self.closest_call = min(self.closest_call, max(0.0, distance - b.radius))
        self.multiplier = min(8.0, self.multiplier + 0.04)
        self.add_score(50 * self.multiplier)
        p.graze_charge += 1
        if p.graze_charge >= self.pc["grazes_per_bomb"]:
            p.graze_charge = 0
            if p.bombs < self.pc["max_bombs"]:
                p.bombs += 1
                self.emit("bomb_charged")
                self.popups.append(Popup(p.x, p.y - 3, "BOMB +1", (120, 255, 255), 1.2))
        for _ in range(2):
            a = random.uniform(0, TAU)
            self.particles.append(Particle((p.x + b.x) / 2, (p.y + b.y) / 2, math.cos(a) * 10, math.sin(a) * 10,
                                           0.25, random.choice(".+'"), (255, 255, 255)))
        self.emit("graze")

    def _on_hit(self) -> None:
        p = self.player
        if self.practice:
            p.iframes = 0.6
            self.emit("hit", practice=True)
            return
        p.lives -= 1
        p.hits_this_phase += 1
        p.iframes = self.pc["iframes"]
        self.multiplier = 1.0
        self.burst(p.x, p.y, (255, 80, 80), 40, 35, "*#x+")
        self.cancel_bullets()
        self.emit("hit", lives=p.lives)
        if p.lives <= 0:
            self.game_over = True
            self.phase = "game_over"
            self.emit("game_over", score=self.score, wave=self.wave_number)

    def _update_fx(self, dt: float) -> None:
        for pt in self.particles:
            pt.x += pt.vx * dt
            pt.y += pt.vy * dt
            pt.vx *= 1 - min(1.0, dt * 2.5)
            pt.vy *= 1 - min(1.0, dt * 2.5)
            pt.life -= dt
        self.particles = [pt for pt in self.particles if pt.life > 0][-800:]
        for pop in self.popups:
            pop.y -= 6 * dt
            pop.life -= dt
        self.popups = [pop for pop in self.popups if pop.life > 0][-40:]

    # ----------------------------------------------------------- queries
    def telegraphs(self):
        """Yield (x, y, angle) for emitters that are charging an aimed shot."""
        owners = list(self.enemies) + ([self.boss] if self.boss else [])
        for owner in owners:
            for em in owner.emitters:
                if em.charging > 0:
                    yield owner.x, owner.y + 1, em.locked_angle, em.charging / max(0.01, em.telegraph_time)
