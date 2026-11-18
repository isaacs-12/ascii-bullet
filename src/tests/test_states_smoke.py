"""Boot the real game headless (SDL dummy driver) and visit every screen."""

import pygame
import pytest

from src.core.game import Game
from src.core.save_system import SaveSystem
from src.states.main_menu import MainMenuState


@pytest.fixture
def game(tmp_path):
    g = Game(save_system=SaveSystem(tmp_path))
    yield g
    pygame.display.quit()


def frames(g, n=3, dt=16):
    for _ in range(n):
        g.update(dt)
        g.render()


def key(g, k, unicode="", mod=0):
    g.current_state.handle_events([pygame.event.Event(pygame.KEYDOWN, key=k, unicode=unicode, mod=mod)])


def ready(g):
    """Skip boot and intro, return the terminal state."""
    g.save_system.data["intro_shown"] = True
    menu = g.current_state
    menu.complete_boot()
    return menu


def type_line(g, text):
    for ch in text:
        key(g, 0, ch)
    key(g, pygame.K_RETURN)


def test_boot_intro_and_terminal(game):
    menu = game.current_state
    assert isinstance(menu, MainMenuState)
    frames(game, 40)
    key(game, pygame.K_SPACE)  # skip boot
    for _ in range(6):  # finish typing + advance both intro pages
        key(game, pygame.K_SPACE)
        frames(game, 2)
    assert game.save_system.has_intro_been_shown()
    type_line(game, "echo hello | rev")
    frames(game, 2)
    assert any(str(line) == "olleh" for line in menu.output_lines)
    screen_text = "\n".join(game.renderer.snapshot_text())
    assert "pilot@blthll" in screen_text


def test_line_editing_keys(game):
    menu = ready(game)
    for ch in "ecxo":
        key(game, 0, ch)
    key(game, pygame.K_LEFT)  # e c x | o
    key(game, pygame.K_BACKSPACE)  # e c | o
    key(game, 0, "h")
    assert menu.input_buffer == "echo"
    key(game, pygame.K_e, mod=pygame.KMOD_CTRL)  # end of line
    key(game, pygame.K_u, mod=pygame.KMOD_CTRL)  # kill to start
    for ch in "cle":
        key(game, 0, ch)
    key(game, pygame.K_TAB)
    assert menu.input_buffer == "clear "


@pytest.mark.parametrize("command", [
    "start", "start demo", "top", "vim notes.txt", "readme /opt/walnut/ai/README.md", "code", "sl", "cmatrix",
])
def test_every_app_launches_renders_and_exits(game, command):
    menu = ready(game)
    type_line(game, command)
    assert game.current_state is not menu, command
    frames(game, 30)
    key(game, pygame.K_ESCAPE)
    frames(game, 2)
    if game.current_state is not menu:  # vim/editor needs :q, gameplay pauses on ESC
        key(game, pygame.K_q)
        key(game, pygame.K_c, mod=pygame.KMOD_CTRL)
        frames(game, 1)
    if game.current_state is not menu:
        game.change_state(menu, call_enter=False)
    frames(game, 2)


@pytest.mark.parametrize("name,unlock", [
    ("minesweeper", "minesweeper"), ("set", "set"), ("oregon", "oregon_trail"), ("spacebullets", None),
])
def test_unlocked_minigames_launch(game, name, unlock):
    menu = ready(game)
    if unlock:
        game.save_system.unlock_game(unlock)
    else:
        game.save_system.mark_virus_killed()
    type_line(game, f"start {name}")
    assert game.current_state is not menu
    frames(game, 20)
    game.change_state(menu, call_enter=False)


def test_locked_games_stay_locked(game):
    menu = ready(game)
    type_line(game, "start set")
    assert game.current_state is menu
    assert any("no such game" in str(line) for line in menu.output_lines)


def test_gameplay_records_a_run(game):
    from src.states.games.gameplay import GameplayState

    menu = ready(game)
    state = GameplayState(game, menu)
    game.change_state(state)
    state.world.player.lives = 1
    from src.bullethell.engine import Bullet

    w = state.world
    w.bullets.append(Bullet(w.player.x, w.player.y, 0, 0, w.content["bullets"]["big"]))
    w.score = 1234
    frames(game, 5)
    assert w.game_over
    assert game.save_system.get_best_score() == 1234
    key(game, pygame.K_q)
    assert game.current_state is menu


def test_theme_switch(game):
    ready(game)
    type_line(game, "theme amber")
    assert game.renderer.theme_name == "amber"
    assert game.save_system.get_setting("theme") == "amber"
    frames(game, 1)
