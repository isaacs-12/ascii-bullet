"""Main game controller: owns the renderer, save data and the active state."""

from __future__ import annotations

import time

import pygame

from src.core.save_system import SaveSystem
from src.core.terminal_renderer import TerminalRenderer

MAX_FRAME_MS = 50  # clamp dt so a window drag or breakpoint can't teleport bullets
PLAYTIME_FLUSH_SECONDS = 30.0


class Game:
    """Top-level loop. States implement handle_events/update/render/enter/exit."""

    def __init__(self, save_system: SaveSystem | None = None, renderer: TerminalRenderer | None = None):
        self.save_system = save_system or SaveSystem()
        self.renderer = renderer or TerminalRenderer(width=160, height=75, cell_size=14)
        self.renderer.crt_enabled = bool(self.save_system.get_setting("crt", True))
        self.renderer.shake_enabled = bool(self.save_system.get_setting("screen_shake", True))
        theme = self.save_system.get_setting("theme")
        if theme:
            self.renderer.set_theme(theme)

        self.running = True
        self.current_state = None
        self.last_playtime_save = time.time()

        # Imported here to avoid a cycle (states import Game indirectly).
        from src.states.main_menu import MainMenuState

        self.change_state(MainMenuState(self))

    def change_state(self, new_state, call_enter: bool = True) -> None:
        if self.current_state:
            self.current_state.exit()
        self.current_state = new_state
        if call_enter:
            self.current_state.enter()

    def handle_events(self) -> None:
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.VIDEORESIZE:
                self.renderer.handle_resize(event.w, event.h)
        if self.current_state:
            self.current_state.handle_events(events)

    def update(self, dt: float) -> None:
        dt = min(dt, MAX_FRAME_MS)
        if self.current_state:
            self.current_state.update(dt)
        self.renderer.update_effects(dt)
        now = time.time()
        if now - self.last_playtime_save >= PLAYTIME_FLUSH_SECONDS:
            self.flush_playtime(now)

    def flush_playtime(self, now: float | None = None) -> None:
        now = now or time.time()
        elapsed = now - self.last_playtime_save
        if elapsed > 0:
            self.save_system.add_playtime(elapsed, "total")
        self.last_playtime_save = now

    def render(self) -> None:
        if self.current_state:
            self.current_state.render()

    def run(self) -> None:
        try:
            while self.running:
                self.handle_events()
                dt = self.renderer.tick(60)
                self.update(dt)
                self.render()
        finally:
            self.flush_playtime()
            if self.current_state:
                self.current_state.exit()
            self.renderer.quit()
