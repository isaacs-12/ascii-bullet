"""Test doubles for exercising the shell without a window."""

from __future__ import annotations

import tempfile

from src.core.save_system import SaveSystem
from src.shell.shell import Shell
from src.unix.filesystem import VirtualFileSystem
from src.unix.process_manager import ProcessManager
from src.unix.systemd_manager import SystemdManager


class StubRenderer:
    def __init__(self):
        self.theme_name = "phosphor"
        self.themes = {"phosphor": {}, "amber": {}}
        self.crt_enabled = True
        self.shake_enabled = True
        self.char_width, self.char_height = 120, 40

    def set_theme(self, name):
        if name in self.themes:
            self.theme_name = name
            return True
        return False

    def flash(self, *a, **k):
        pass

    def shake(self, *a, **k):
        pass


class StubGame:
    def __init__(self, save_dir=None):
        self.save_system = SaveSystem(save_dir or tempfile.mkdtemp(prefix="blthll-test-"))
        self.renderer = StubRenderer()
        self.running = True


class FakeUI:
    width = 120

    def __init__(self):
        self.lines: list = []
        self.launched: list = []
        self.notifications: list = []
        self.quit_called = False

    def write(self, line):
        self.lines.append(line)

    def typed(self, lines, delay=30):
        self.lines.extend(lines)

    def clear(self):
        self.lines.clear()

    def launch(self, factory):
        self.launched.append(factory)

    def quit(self):
        self.quit_called = True

    def notify(self, title, body):
        self.notifications.append(body)

    def text(self) -> str:
        return "\n".join(str(x) for x in self.lines)

    def take(self) -> str:
        out = self.text()
        self.lines.clear()
        return out


def make_shell(save_dir=None):
    game = StubGame(save_dir)
    fs = VirtualFileSystem()
    pm = ProcessManager(save_system=game.save_system)
    sd = SystemdManager(fs, save_system=game.save_system)
    ui = FakeUI()
    shell = Shell(game, fs, pm, sd, ui)
    return shell, ui
