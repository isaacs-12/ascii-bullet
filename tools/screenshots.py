#!/usr/bin/env python3
"""Regenerate the README screenshots headlessly.

    SDL_VIDEODRIVER=dummy python tools/screenshots.py docs/screenshots
"""

from __future__ import annotations

import os
import random
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ["ASCII_BULLET_SAVE_DIR"] = tempfile.mkdtemp(prefix="blthll-shots-")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame  # noqa: E402

from src.core.game import Game  # noqa: E402
from src.states.games.gameplay import GameplayState  # noqa: E402

SIZE = (1280, 800)


def main(out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    random.seed(7)
    game = Game()
    game.renderer.handle_resize(*SIZE)
    game.save_system.data["intro_shown"] = True
    menu = game.current_state

    def frames(n: int) -> None:
        for _ in range(n):
            game.update(16)
            game.render()

    def key(k, uni="", mod=0) -> None:
        game.current_state.handle_events([pygame.event.Event(pygame.KEYDOWN, key=k, unicode=uni, mod=mod)])

    def type_line(text: str) -> None:
        for ch in text:
            key(0, ch)
        key(pygame.K_RETURN)
        frames(2)

    def shot(name: str) -> None:
        game.render()
        pygame.image.save(game.renderer.screen, str(out / f"{name}.png"))
        print("wrote", out / f"{name}.png")

    menu.complete_boot()
    frames(5)
    for line in ["ls -la", "ls /opt/walnut/ai && echo $API_KEY", "fortune | cowsay | lolcat", "neofetch"]:
        type_line(line)
        frames(120)
    shot("terminal")

    type_line("clear")
    type_line("claude")
    frames(10)
    for prompt in ["are you real?", "fix the laser service", "any hints? I'm stuck"]:
        type_line(prompt)
        frames(400)
    shot("ai")
    key(pygame.K_c, mod=pygame.KMOD_CTRL)

    state = GameplayState(game, menu, demo=True)
    game.change_state(state)
    for _ in range(60 * 34):
        game.update(16)
    shot("wave")
    world = state.world
    for _ in range(60 * 240):
        game.update(16)
        boss = world.boss
        if boss and boss.phase_index == 2 and boss.phase_time > 9:
            break
    shot("boss")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "docs/screenshots")
