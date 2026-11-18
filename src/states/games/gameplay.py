"""BLTHLL: the bullet hell itself. Draws a ``World`` and turns its events into juice."""

from __future__ import annotations

import math
import random

import pygame

from src.bullethell.autopilot import autopilot
from src.bullethell.engine import InputState, World
from src.core.achievements import AchievementTracker
from src.shell.registry import load_json
from src.states.base_state import BaseState

HUD_WIDTH = 30
GRAZE_ACHIEVEMENT = 150
SURVIVOR_SECONDS = 180


class GameplayState(BaseState):
    def __init__(self, game, previous_state=None, start_wave: int = 1, practice: bool = False,
                 demo: bool = False):
        super().__init__(game)
        self.previous_state = previous_state
        self.start_wave = max(1, start_wave)
        self.demo = demo  # attract mode: the autopilot plays, nothing is recorded
        self.practice = practice or demo
        self.save = game.save_system
        shell = getattr(previous_state, "shell", None)
        self.achievements = shell.achievements if shell else AchievementTracker(self.save)
        self.font_art = load_json("art.json")["block_font"]
        self._new_run()

    def _new_run(self, start_wave: int | None = None) -> None:
        self.world = World(start_wave=start_wave or self.start_wave, practice=self.practice)
        self.paused = False
        self.finished = False
        self.banner: tuple[str, str, float] | None = None  # (big text, subtitle, remaining)
        self.toasts: list[list] = []
        self.flash_cells = 0.0
        self.is_new_high = False
        self.best_before = self.save.get_best_score()
        self.stars = [[random.uniform(0, self.world.width), random.uniform(0, self.world.height),
                       random.uniform(4, 16)] for _ in range(70)]
        self.t = 0.0
        self.bomb_pressed = False

    # -------------------------------------------------------- lifecycle
    def enter(self) -> None:
        self._previous_unlock = self.achievements.on_unlock
        self.achievements.on_unlock = lambda a: self.toasts.append([a["name"], 3.0])

    def exit(self) -> None:
        self.achievements.on_unlock = getattr(self, "_previous_unlock", None)

    def _leave(self) -> None:
        self._finish_run()
        if self.previous_state:
            self.game.change_state(self.previous_state, call_enter=False)
        else:
            from src.states.main_menu import MainMenuState

            self.game.change_state(MainMenuState(self.game))

    def _finish_run(self) -> None:
        """Record score and stats once per run (game over or quitting mid-run)."""
        if self.finished:
            return
        self.finished = True
        w = self.world
        save = self.save
        save.add_playtime(w.time_alive, "bullet_hell")
        if self.practice:
            return
        if w.score > 0:
            self.is_new_high = w.score > self.best_before
            save.add_score(w.score, int(w.time_alive * 1000), w.wave_number)
        stats = save.data["stats"]
        stats["grazes"] = stats.get("grazes", 0) + w.grazes
        stats["bombs_used"] = stats.get("bombs_used", 0) + w.bombs_used
        stats["bosses_defeated"] = stats.get("bosses_defeated", 0) + w.bosses_defeated
        stats["enemies_depleted"] = stats.get("enemies_depleted", 0) + w.enemies_depleted
        stats["best_wave"] = max(stats.get("best_wave", 0), w.wave_number)
        stats["closest_call"] = min(stats.get("closest_call", 999), w.closest_call)
        save.save()

    def _achieve(self, achievement_id: str) -> None:
        if not self.practice:  # godmode and demo runs don't earn achievements
            self.achievements.unlock(achievement_id)

    # ------------------------------------------------------------ input
    def handle_events(self, events) -> None:
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            key = event.key
            if (key == pygame.K_c and event.mod & pygame.KMOD_CTRL) or (self.demo and not self.world.game_over):
                self._leave()
                return
            if self.world.game_over:
                if key in (pygame.K_r, pygame.K_RETURN):
                    self._new_run(1)
                elif key == pygame.K_c and self.save.get_checkpoint_wave() > 1:
                    self._new_run(self.save.get_checkpoint_wave())
                elif key in (pygame.K_q, pygame.K_ESCAPE):
                    self._leave()
                    return
            elif self.paused:
                if key in (pygame.K_p, pygame.K_ESCAPE, pygame.K_RETURN):
                    self.paused = False
                elif key == pygame.K_q:
                    self._leave()
                    return
                elif key == pygame.K_r:
                    self._finish_run()
                    self._new_run(1)
            else:
                if key in (pygame.K_p, pygame.K_ESCAPE):
                    self.paused = True
                elif key in (pygame.K_x, pygame.K_SPACE, pygame.K_b):
                    self.bomb_pressed = True

    def _read_input(self) -> InputState:
        if self.demo:
            return autopilot(self.world)
        keys = pygame.key.get_pressed()
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        focus = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] or keys[pygame.K_z])
        inp = InputState(float(dx), float(dy), focus, self.bomb_pressed)
        self.bomb_pressed = False
        return inp

    # ----------------------------------------------------------- update
    def update(self, dt: float) -> None:
        self.t += dt / 1000.0
        for toast in self.toasts:
            toast[1] -= dt / 1000.0
        self.toasts = [t for t in self.toasts if t[1] > 0]
        if self.paused:
            return
        sec = dt / 1000.0
        self.world.update(sec, self._read_input())
        for star in self.stars:
            star[1] += star[2] * sec * (2.5 if self.world.phase == "intermission" else 1.0)
            if star[1] > self.world.height:
                star[0], star[1] = random.uniform(0, self.world.width), 0.0
        if self.banner:
            self.banner = (self.banner[0], self.banner[1], self.banner[2] - sec)
            if self.banner[2] <= 0:
                self.banner = None
        self.flash_cells = max(0.0, self.flash_cells - sec)
        self._handle_events()

    def _handle_events(self) -> None:
        r = self.renderer
        w = self.world
        for ev in w.drain_events():
            k = ev.kind
            if k == "wave_start":
                loop = ev.data["loop"]
                sub = f"LOOP {loop + 1}  -  speed +{int((w.speed_mult - 1) * 100)}%" if loop else "get ready"
                self.banner = (f"WAVE {ev.data['wave']}", sub, 2.0)
            elif k == "boss_warning":
                self.banner = ("WARNING", f"{ev.data['name']} approaching", 2.6)
                r.shake(3, 2.0)
            elif k == "boss_phase":
                self.banner = (f"PHASE {ev.data['index'] + 1}", f'"{ev.data["phase"]}"', 1.6)
            elif k == "boss_phase_cleared":
                if ev.data["captured"]:
                    self.toasts.append(["CAPTURE BONUS!", 2.0])
                    self._achieve("untouchable")
            elif k == "boss_defeated":
                r.flash((255, 255, 255), 0.5)
                r.shake(12, 1.0)
                self.banner = ("DEFEATED", ev.data["name"], 2.6)
                self._achieve("boss_slayer")
                if not self.practice:
                    self.save.set_checkpoint_wave(ev.data["wave"] + 1)
                    self.toasts.append([f"Checkpoint saved: wave {ev.data['wave'] + 1}", 2.5])
            elif k == "loop":
                self._achieve("loop_two")
            elif k == "hit":
                if ev.data.get("practice"):
                    r.flash((255, 255, 0), 0.08)
                else:
                    r.flash((255, 40, 40), 0.35)
                    r.shake(10, 0.45)
                    self.flash_cells = 0.3
            elif k == "bomb":
                r.flash((200, 255, 255), 0.25)
                r.shake(6, 0.5)
                self._achieve("bomb_squad")
            elif k == "bomb_charged":
                self.toasts.append(["Bomb charged", 1.5])
            elif k == "game_over":
                r.shake(14, 0.8)
                self._finish_run()
                self.banner = None
        if w.grazes >= GRAZE_ACHIEVEMENT:
            self._achieve("graze_master")
        if w.time_alive >= SURVIVOR_SECONDS and not w.game_over:
            self._achieve("survivor")

    # ----------------------------------------------------------- layout
    def _layout(self):
        r = self.renderer
        aspect = r.cell_height / max(1, r.cell_width)
        w, h = self.world.width, self.world.height
        avail_cols = r.char_width - HUD_WIDTH - 4
        avail_rows = r.char_height - 2
        scale = min(1.0, avail_cols / w, avail_rows / (h / aspect))
        cols = max(10, int(w * scale))
        rows = max(6, int(h * scale / aspect))
        total = cols + 2 + 1 + HUD_WIDTH
        ox = max(1, (r.char_width - total) // 2 + 1)
        oy = max(1, (r.char_height - rows - 2) // 2 + 1)
        return ox, oy, cols, rows, scale, aspect

    # ----------------------------------------------------------- render
    def render(self) -> None:
        r = self.renderer
        r.clear()
        ox, oy, cols, rows, scale, aspect = self._layout()
        w = self.world
        colors = r.COLORS

        def cell(x, y):
            return ox + int(x * scale), oy + int(y * scale / aspect)

        def inside(cx, cy):
            return ox <= cx < ox + cols and oy <= cy < oy + rows

        def put(x, y, text, color, bg=None):
            cx, cy = cell(x, y)
            for i, ch in enumerate(text):
                if inside(cx + i, cy):
                    r.write(cx + i, cy, ch, color, bg)

        # arena + background
        border = colors["error"] if self.flash_cells > 0 else colors["dim"]
        r.draw_box(ox - 1, oy - 1, cols + 2, rows + 2, border, style="line")
        for sx, sy, sp in self.stars:
            put(sx, sy, "." if sp < 10 else "·", (40, 40, 60) if sp < 10 else (80, 80, 110))

        # telegraphs: dotted aim lines before a sniper shot
        for tx, ty, ang, frac in w.telegraphs():
            color = (255, 60, 60) if frac < 0.35 else (110, 40, 40)
            for step in range(4, 120, 4):
                put(tx + math.cos(ang) * step, ty + math.sin(ang) * step, "·", color)

        # bomb shockwave
        if w.bomb_time > 0:
            p = w.player
            for i in range(48):
                a = i / 48 * math.tau
                put(p.x + math.cos(a) * w.bomb_radius, p.y + math.sin(a) * w.bomb_radius, "*", (200, 255, 255))

        for b in w.bullets:
            put(b.x, b.y, b.display_glyph(), b.color)

        for e in w.enemies:
            color = (255, 255, 255) if e.flash > 0 else (e.color if e.state != "exit" else (90, 90, 90))
            self._put_art(put, e.x, e.y, e.art, color, scale, aspect)
            if e.state == "exit" and e.depleted:
                put(e.x - 4, e.y - 2.5, "depleted", (90, 140, 90))

        if w.boss:
            boss = w.boss
            color = (255, 255, 255) if boss.flash > 0 else boss.color
            self._put_art(put, boss.x, boss.y, boss.art, color, scale, aspect)

        self._render_player(put, aspect, scale)

        for pt in w.particles:
            fade = max(0.25, pt.life / pt.max_life)
            put(pt.x, pt.y, pt.glyph, tuple(int(c * fade) for c in pt.color))
        for pop in w.popups:
            put(pop.x - len(pop.text) / 2, pop.y, pop.text, pop.color)

        self._render_hud(ox + cols + 2, oy - 1, rows + 2)
        if self.banner and not w.game_over:
            self._render_banner(ox, oy, cols, rows)
        if self.paused:
            self._render_panel(ox, oy, cols, rows, "PAUSED",
                               ["P / ESC   resume", "R         restart from wave 1", "Q         quit to terminal"])
        if w.game_over:
            self._render_game_over(ox, oy, cols, rows)
        self._render_toasts(ox, oy, cols)
        r.render()

    @staticmethod
    def _put_art(put, x: float, y: float, art: list[str], color, scale: float, aspect: float) -> None:
        """Draw multi-line art centred on (x, y); one text row is aspect/scale world units tall."""
        row_h = aspect / scale
        for i, line in enumerate(art):
            put(x - len(line) / 2 / scale, y + (i - (len(art) - 1) / 2) * row_h, line, color)

    def _render_player(self, put, aspect: float, scale: float) -> None:
        w = self.world
        p = w.player
        if w.game_over:
            return
        blink = p.iframes > 0 and int(self.t * 12) % 2 == 0
        if blink:
            return
        ship = (120, 255, 160) if not self.practice else (255, 230, 90)
        put(p.x - 1.5 / scale, p.y, "/A\\", ship)
        if p.focus:
            put(p.x - 0.5 / scale, p.y, "•", (255, 255, 255))
            ring = w.pc["graze"]
            for i in range(16):
                a = i / 16 * math.tau
                put(p.x + math.cos(a) * ring, p.y + math.sin(a) * ring, "·", (70, 110, 90))

    def _block_text(self, text: str) -> list[str]:
        rows = [""] * 5
        for ch in text.upper():
            glyph = self.font_art.get(ch, self.font_art["?"])
            for i in range(5):
                rows[i] += glyph[i].replace("#", "█") + " "
        return [row.rstrip() for row in rows]

    def _render_banner(self, ox, oy, cols, rows) -> None:
        r = self.renderer
        big, sub, remaining = self.banner
        art = self._block_text(big)
        y = oy + rows // 3
        hue_color = (255, 80, 80) if big == "WARNING" else r.COLORS["title"]
        if big == "WARNING" and int(self.t * 6) % 2:
            hue_color = (255, 200, 60)
        width = max(len(line) for line in art)
        if width <= cols:
            x = ox + (cols - width) // 2
            for i, line in enumerate(art):
                for j, ch in enumerate(line):
                    if ch != " ":
                        r.write(x + j, y + i, ch, hue_color)
            y += 6
        else:
            r.write(ox + (cols - len(big)) // 2, y, big, hue_color)
            y += 2
        r.write(ox + max(0, (cols - len(sub)) // 2), y, sub[:cols], r.COLORS["menu_normal"])

    def _render_panel(self, ox, oy, cols, rows, title, lines) -> None:
        r = self.renderer
        width = min(cols - 4, max(len(title), *(len(x) for x in lines)) + 8)
        height = len(lines) + 5
        x = ox + (cols - width) // 2
        y = oy + (rows - height) // 2
        bg = (12, 12, 24)
        r.fill_bg(x, y, width, height, bg)
        for row in range(y, y + height):
            r.write(x, row, " " * width, bg=bg)
        r.draw_box(x, y, width, height, r.COLORS["accent"], style="double")
        r.write(x + (width - len(title)) // 2, y + 1, title, r.COLORS["title"])
        for i, line in enumerate(lines):
            r.write(x + 3, y + 3 + i, line, r.COLORS["menu_normal"] if line else r.COLORS["fg"])

    def _render_game_over(self, ox, oy, cols, rows) -> None:
        w = self.world
        lines = [
            f"SCORE   {w.score:,}",
            f"WAVE    {w.wave_number}" + (f"  (loop {w.loop + 1})" if w.loop else ""),
            f"GRAZES  {w.grazes}",
            f"TIME    {int(w.time_alive // 60)}:{int(w.time_alive % 60):02d}",
            "",
        ]
        if self.is_new_high:
            lines.insert(0, "*** NEW HIGH SCORE ***")
        if self.practice:
            lines.insert(0, "(godmode run: not recorded)")
        lines += ["R  retry from wave 1"]
        if self.save.get_checkpoint_wave() > 1:
            lines += [f"C  continue from wave {self.save.get_checkpoint_wave()}"]
        lines += ["Q  back to terminal"]
        self._render_panel(ox, oy, cols, rows, "GAME OVER", lines)

    def _bar(self, frac: float, width: int) -> str:
        filled = int(round(max(0.0, min(1.0, frac)) * width))
        return "█" * filled + "░" * (width - filled)

    def _render_hud(self, x: int, y: int, height: int) -> None:
        r = self.renderer
        c = r.COLORS
        w = self.world
        p = w.player
        r.draw_box(x, y, HUD_WIDTH, height, c["dim"], style="line")
        row = y + 1

        def line(text="", color=None, label=None):
            nonlocal row
            if row >= y + height - 1:
                return
            if label is not None:
                r.write(x + 2, row, label.ljust(8), c["dim"])
                r.write(x + 10, row, str(text)[: HUD_WIDTH - 12], color or c["fg"])
            else:
                r.write(x + 2, row, str(text)[: HUD_WIDTH - 4], color or c["fg"])
            row += 1

        line("B L T H L L", c["title"])
        line("─" * (HUD_WIDTH - 4), c["dim"])
        line(f"{w.score:,}", c["menu_selected"], "SCORE")
        hi = max(self.best_before, w.score)
        line(f"{hi:,}", c["warn"] if w.score >= hi and w.score else c["fg"], "HI")
        mult_color = c["accent"] if w.multiplier > 1.5 else c["fg"]
        line(f"x{w.multiplier:.2f}", mult_color, "MULT")
        line(f"{w.grazes}", c["fg"], "GRAZE")
        line()
        line(" ".join("♥" for _ in range(max(0, p.lives))) or "-", (255, 90, 110), "LIVES")
        line(" ".join("✦" for _ in range(p.bombs)) or "-", (120, 230, 255), "BOMBS")
        charge = p.graze_charge / max(1, w.pc["grazes_per_bomb"])
        line(self._bar(charge, 12), (80, 160, 200), "CHARGE")
        line()
        loop_txt = f"  loop {w.loop + 1}" if w.loop else ""
        line(f"{w.wave_number}{loop_txt}", c["fg"], "WAVE")
        if self.demo:
            line("DEMO - any key exits", c["warn"])
        elif self.practice:
            line("GODMODE (QA build)", c["warn"])
        line()
        if w.boss and w.boss.phase_index >= 0:
            boss = w.boss
            line(boss.name, boss.color)
            line(f"phase {boss.phase_index + 1}/{len(boss.phases)}", c["dim"])
            line(f'"{boss.phase["name"]}"'[: HUD_WIDTH - 4], c["menu_normal"])
            remaining = boss.phase["duration"] - boss.phase_time
            line(self._bar(boss.phase_fraction(), HUD_WIDTH - 10) + f" {int(remaining):>2}s", boss.color)
            line("survive the timer!", c["dim"])
        elif w.phase == "wave":
            line(f"enemies {len(w.enemies)}", c["dim"])
        line()
        row = max(row, y + height - 8)
        line("arrows/wasd  move", c["dim"])
        line("shift        focus", c["dim"])
        line("x / space    bomb", c["dim"])
        line("p / esc      pause", c["dim"])
        line("ctrl+c       quit", c["dim"])

    def _render_toasts(self, ox, oy, cols) -> None:
        r = self.renderer
        for i, (text, remaining) in enumerate(self.toasts[-3:]):
            msg = f" {text} "
            color = r.COLORS["warn"] if remaining > 0.5 or int(remaining * 10) % 2 else r.COLORS["dim"]
            r.write(ox + (cols - len(msg)) // 2, oy + 1 + i, msg, color, bg=(30, 25, 5))
