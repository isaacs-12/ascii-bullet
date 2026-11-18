"""Full-screen terminal toys: `sl` (a train) and `cmatrix` (digital rain)."""

from __future__ import annotations

import random

import pygame

from src.shell.registry import load_json
from src.states.base_state import BaseState

_RAIN_CHARS = "01ﾊﾐﾋｰｳｼﾅﾓﾆｻﾜﾂｵﾘｱﾎﾃﾏｹﾒｴｶｷﾑﾕﾗｾﾈｽﾀﾇﾍ$#@%&*+=<>"
_ASCII_RAIN = "01$#@%&*+=<>abcdefxyz/\\|"


class FxState(BaseState):
    """Plays an animation, then returns to ``previous_state``. Any key exits rain."""

    def __init__(self, game, previous_state, mode: str):
        super().__init__(game)
        self.previous_state = previous_state
        self.mode = mode
        self.t = 0.0
        art = load_json("art.json")
        self.train = art["train"]
        self.train_x = float(self.renderer.char_width)
        self.drops: list[list[float]] = []
        # Half-width katakana need a font that has them; fall back to ASCII.
        has_kana = self.renderer.font.metrics("ﾊ")[0] is not None
        self.charset = _RAIN_CHARS if has_kana else _ASCII_RAIN

    def _done(self) -> None:
        self.game.change_state(self.previous_state, call_enter=False)

    def handle_events(self, events) -> None:
        for event in events:
            if event.type == pygame.KEYDOWN:
                ctrl_c = event.key == pygame.K_c and event.mod & pygame.KMOD_CTRL
                # Like the real sl, the train can't be interrupted (except by Ctrl+C here, we're nice).
                if self.mode == "rain" or ctrl_c or event.key == pygame.K_ESCAPE:
                    self._done()
                    return

    def update(self, dt: float) -> None:
        self.t += dt / 1000.0
        if self.mode == "train":
            self.train_x -= dt / 1000.0 * 45
            if self.train_x < -max(len(x) for x in self.train) - 2:
                self._done()
        else:
            w = self.renderer.char_width
            if len(self.drops) < w // 2 and random.random() < 0.9:
                self.drops.append([random.randrange(w), -random.random() * 10, random.uniform(12, 35),
                                   random.randint(6, 24)])
            for d in self.drops:
                d[1] += d[2] * dt / 1000.0
            h = self.renderer.char_height
            self.drops = [d for d in self.drops if d[1] - d[3] < h]

    def render(self) -> None:
        r = self.renderer
        r.clear()
        if self.mode == "train":
            top = max(0, r.char_height // 2 - len(self.train) // 2)
            x = int(self.train_x)
            puff = int(self.t * 6) % 2
            for i, line in enumerate(self.train):
                if i < 4 and puff:
                    line = " " * 2 + line  # smoke drifts
                r.write(x, top + i, line, r.COLORS["fg"])
            r.write_centered(r.char_height - 2, "(you typed sl. there is no escape. well, Ctrl+C.)", r.COLORS["dim"])
        else:
            for col, y, _speed, length in self.drops:
                head = int(y)
                for k in range(length):
                    row = head - k
                    if 0 <= row < r.char_height:
                        if k == 0:
                            color = (220, 255, 220)
                        else:
                            fade = max(40, 255 - k * (215 // max(1, length)))
                            color = (0, fade, 60 if k < 3 else 0)
                        r.write(col, row, random.choice(self.charset) if k == 0 or random.random() < 0.05
                                else self.charset[(col * 7 + row * 13) % len(self.charset)], color)
            if self.t < 3:
                r.write_centered(r.char_height // 2, " Wake up, pilot... ", (180, 255, 180), bg=(0, 20, 0))
        r.render()
