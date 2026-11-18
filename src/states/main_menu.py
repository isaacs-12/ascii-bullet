"""
The terminal: boot sequence, intro, scrollback, line editing and toasts.

All command behaviour lives in ``src/shell``; this state only displays the
shell and feeds it keystrokes.
"""

from __future__ import annotations

import colorsys

import pygame

from src.shell.registry import load_json
from src.shell.shell import InputSession, Shell
from src.shell.text import Styled, columns, wrap_line
from src.states.base_state import BaseState
from src.unix.filesystem import VirtualFileSystem
from src.unix.process_manager import ProcessManager
from src.unix.systemd_manager import SystemdManager

MAX_SCROLLBACK = 2000
KONAMI = ["up", "up", "down", "down", "left", "right", "left", "right", "b", "a"]
TOAST_MS = 3500


def _truncate(line, n: int):
    """First ``n`` characters of a str/Styled line (for the typing animation)."""
    if not isinstance(line, Styled):
        return str(line)[:n]
    out, left = [], n
    for text, color in line.segments:
        if left <= 0:
            break
        out.append((text[:left], color))
        left -= len(text)
    return Styled(*out)


class MainMenuState(BaseState):
    """Terminal-style command interface."""

    def __init__(self, game):
        super().__init__(game)
        self.dialogue = load_json("dialogue.json")
        save = game.save_system

        self.filesystem = VirtualFileSystem(saved_state=save.get_filesystem_state())
        self.process_manager = ProcessManager(save_system=save)
        self.systemd_manager = SystemdManager(self.filesystem, save_system=save)
        self.shell = Shell(game, self.filesystem, self.process_manager, self.systemd_manager, self)

        self.output_lines: list = []
        self.input_buffer = ""
        self.cursor_pos = 0
        self.cursor_visible = True
        self.cursor_timer = 0.0
        self.scroll_offset = 0
        self.history_index = -1
        self.saved_draft = ""

        # Animated typing
        self.typing_queue: list = []
        self.typing_line = None
        self.typing_index = 0
        self.typing_acc = 0.0
        self.typing_delay = 30

        # Boot / intro
        self.booting = True
        self.boot_index = 0
        self.boot_timer = 0.0
        self.boot_delay = 110
        self.showing_intro = False
        self.intro_page = 0

        self.toasts: list[list] = []  # [title, body, remaining_ms]
        self.konami_sequence: list[str] = []

    # ----------------------------------------------------------- ShellUI
    @property
    def width(self) -> int:
        return max(20, self.renderer.char_width - 2)

    def write(self, line) -> None:
        self.output_lines.extend(wrap_line(line, self.width))
        if len(self.output_lines) > MAX_SCROLLBACK:
            del self.output_lines[: len(self.output_lines) - MAX_SCROLLBACK]

    add_output = write  # legacy name used by older states

    def typed(self, lines, delay: int = 30) -> None:
        for line in lines:
            self.typing_queue.extend(wrap_line(line, self.width))
        self.typing_delay = max(1, delay)

    def clear(self) -> None:
        self.output_lines = []
        self.scroll_offset = 0

    def launch(self, factory) -> None:
        self._finish_typing()
        self.game.change_state(factory(self.game, self))

    def quit(self) -> None:
        self.game.save_system.save_command_history(self.shell.history)
        self.game.running = False

    def notify(self, title: str, body: str) -> None:
        self.toasts.append([title, body, TOAST_MS])

    # Legacy hooks used by editor states.
    def _save_filesystem(self) -> None:
        self.shell.save_filesystem()

    def get_prompt(self) -> str:
        return self.shell.prompt_text()

    @property
    def command_history(self) -> list[str]:
        return self.shell.history

    # -------------------------------------------------------- lifecycle
    def enter(self) -> None:
        self.booting = True
        self.boot_index = 0
        self.boot_timer = 0.0
        self.output_lines = []

    def exit(self) -> None:
        self.game.save_system.save_command_history(self.shell.history)

    def complete_boot(self) -> None:
        self.booting = False
        self.output_lines = []
        save = self.game.save_system
        if save.should_prompt_for_existing_save():
            self._show_save_prompt()
        elif not save.has_intro_been_shown():
            self._start_intro(0)
        else:
            self._show_main_screen()

    def _show_save_prompt(self) -> None:
        self.typed(self.dialogue["save_prompt"], 15)
        save = self.game.save_system

        def on_line(line: str) -> bool:
            answer = line.strip().lower()
            if answer in ("y", "yes"):
                save.mark_save_prompt_shown()
                self.write("Loading existing save...")
            elif answer in ("n", "no"):
                save.reset_save()
                save.mark_save_prompt_shown()
                self.filesystem.reset_to_defaults()
                self.shell.history.clear()
                self.write("Starting fresh...")
            else:
                self.write("Please type 'yes' or 'no'.")
                return True
            if not save.has_intro_been_shown():
                self._start_intro(0)
            else:
                self._show_main_screen()
            return False

        self.shell.session = InputSession(prompt="> ", on_line=on_line)

    def _start_intro(self, page: int) -> None:
        self.showing_intro = True
        self.intro_page = page
        self.output_lines = []
        self.typed(self.dialogue["intro_pages"][page], 12)

    def _show_main_screen(self) -> None:
        self.showing_intro = False
        for i, line in enumerate(self.dialogue["title_art"]):
            r, g, b = colorsys.hsv_to_rgb((0.28 + i * 0.035) % 1.0, 0.85, 1.0)
            self.write(Styled.plain(line, (int(r * 255), int(g * 255), int(b * 255))))
        self.write("")
        for i, line in enumerate(self.dialogue["welcome"]):
            self.write(Styled.plain(line, "title" if i == 0 else "dim"))
        best = self.game.save_system.get_best_score()
        found, _total = self.shell.achievements.summary()
        if best or found:
            self.write(Styled.plain(f"Best score: {best:,}   Achievements: {found}/{_total}", "dim"))
            self.write("")
        self.game.save_system.mark_directory_visited(self.filesystem.get_pwd())

    # ----------------------------------------------------------- typing
    @property
    def is_typing(self) -> bool:
        return self.typing_line is not None or bool(self.typing_queue)

    def _finish_typing(self) -> None:
        if self.typing_line is not None:
            self.output_lines[-1] = self.typing_line
            self.typing_line = None
        for line in self.typing_queue:
            self.write(line)
        self.typing_queue = []

    def _update_typing(self, dt: float) -> None:
        if self.typing_line is None:
            if not self.typing_queue:
                self.typing_acc = 0.0
                return
            self.typing_line = self.typing_queue.pop(0)
            self.typing_index = 0
            self.output_lines.append("")
        self.typing_acc += dt
        steps = int(self.typing_acc // self.typing_delay)
        if steps <= 0:
            return
        self.typing_acc -= steps * self.typing_delay
        self.typing_index += steps
        if self.typing_index >= len(self.typing_line):
            self.output_lines[-1] = self.typing_line
            self.typing_line = None
        else:
            self.output_lines[-1] = _truncate(self.typing_line, self.typing_index)

    # ----------------------------------------------------------- events
    def handle_events(self, events) -> None:
        for event in events:
            if event.type == pygame.MOUSEWHEEL:
                self._scroll(event.y * 3)
            elif event.type == pygame.KEYDOWN:
                self._on_key(event)

    def _on_key(self, event) -> None:
        if self.booting:
            self.complete_boot()
            return
        if self.showing_intro:
            if self.is_typing:
                self._finish_typing()
            elif self.intro_page + 1 < len(self.dialogue["intro_pages"]):
                self._start_intro(self.intro_page + 1)
            else:
                self.game.save_system.mark_intro_shown()
                self.output_lines = []
                self._show_main_screen()
            return

        self._track_konami(event)
        ctrl = event.mod & pygame.KMOD_CTRL
        key = event.key

        if self.is_typing and key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
            self._finish_typing()
            if key == pygame.K_ESCAPE:
                return

        if ctrl:
            if key == pygame.K_c:
                self.write(Styled((self.shell.prompt_text() + self._display_input(), None), ("^C", "dim")))
                self.shell.cancel_session()
                self._set_input("")
            elif key == pygame.K_l:
                self.clear()
            elif key == pygame.K_u:
                self._set_input(self.input_buffer[self.cursor_pos:], 0)
            elif key == pygame.K_a:
                self.cursor_pos = 0
            elif key == pygame.K_e:
                self.cursor_pos = len(self.input_buffer)
            elif key == pygame.K_w:
                head = self.input_buffer[: self.cursor_pos].rstrip()
                cut = head.rfind(" ") + 1
                self._set_input(self.input_buffer[:cut] + self.input_buffer[self.cursor_pos:], cut)
            return

        b, pos = self.input_buffer, self.cursor_pos
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._submit()
        elif key == pygame.K_BACKSPACE:
            if pos > 0:
                self._set_input(b[: pos - 1] + b[pos:], pos - 1)
        elif key == pygame.K_DELETE:
            self._set_input(b[:pos] + b[pos + 1:], pos)
        elif key == pygame.K_LEFT:
            self.cursor_pos = max(0, pos - 1)
        elif key == pygame.K_RIGHT:
            self.cursor_pos = min(len(b), pos + 1)
        elif key == pygame.K_UP:
            self._scroll(1) if event.mod & pygame.KMOD_SHIFT else self._history(1)
        elif key == pygame.K_DOWN:
            self._scroll(-1) if event.mod & pygame.KMOD_SHIFT else self._history(-1)
        elif key == pygame.K_PAGEUP:
            self._scroll(self._visible_rows() - 1)
        elif key == pygame.K_PAGEDOWN:
            self._scroll(-(self._visible_rows() - 1))
        elif key == pygame.K_HOME:
            self.scroll_offset = self._max_scroll()
        elif key == pygame.K_END:
            self.scroll_offset = 0
        elif key == pygame.K_TAB:
            self._complete()
        elif key == pygame.K_ESCAPE:
            self._set_input("")
            self.history_index = -1
        elif event.unicode and event.unicode.isprintable() and len(b) < 400:
            self._set_input(b[:pos] + event.unicode + b[pos:], pos + 1)
            self.history_index = -1

    def _set_input(self, text: str, cursor: int | None = None) -> None:
        self.input_buffer = text
        self.cursor_pos = len(text) if cursor is None else max(0, min(cursor, len(text)))
        self.cursor_visible = True
        self.cursor_timer = 0.0

    def _display_input(self) -> str:
        session = self.shell.session
        return "" if session and session.secret else self.input_buffer

    def _submit(self) -> None:
        line = self.input_buffer
        self.write(Styled(*self.shell.prompt_segments(), (self._display_input(), None)))
        self._set_input("")
        self.history_index = -1
        self.scroll_offset = 0
        self.shell.submit(line)

    def _history(self, direction: int) -> None:
        history = self.shell.history
        if self.shell.session or not history:
            return
        if self.history_index == -1:
            self.saved_draft = self.input_buffer
        self.history_index = max(-1, min(len(history) - 1, self.history_index + direction))
        self._set_input(self.saved_draft if self.history_index == -1 else history[-(self.history_index + 1)])

    def _complete(self) -> None:
        head, tail = self.input_buffer[: self.cursor_pos], self.input_buffer[self.cursor_pos:]
        new_head, options = self.shell.complete(head)
        if options:
            self.write(Styled(*self.shell.prompt_segments(), (self.input_buffer, None)))
            for row in columns(options, self.width):
                self.write(Styled.plain(row, "accent"))
        self._set_input(new_head + tail, len(new_head))

    def _track_konami(self, event) -> None:
        arrows = {pygame.K_UP: "up", pygame.K_DOWN: "down", pygame.K_LEFT: "left", pygame.K_RIGHT: "right"}
        uni = (event.unicode or "").lower()
        name = arrows.get(event.key) or (uni if uni in ("a", "b") else None)
        if not name:
            self.konami_sequence = []
            return
        self.konami_sequence = (self.konami_sequence + [name])[-len(KONAMI):]
        if self.konami_sequence == KONAMI:
            self.konami_sequence = []
            self._set_input("")
            self.typed(["", "...", "Psh, your powers don't work here.",
                        "This is a bullet hell, not a run-and-gun!", ""], 30)
            self.shell.achievements.unlock("konami_keys")
            self.renderer.shake(5, 0.3)

    # ------------------------------------------------------------ update
    def update(self, dt: float) -> None:
        self.cursor_timer += dt
        if self.cursor_timer >= 530:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0.0

        if self.booting:
            self.boot_timer += dt
            boot = self.dialogue["boot"]
            while self.booting and self.boot_timer >= self.boot_delay:
                if self.boot_index < len(boot):
                    self.boot_timer -= self.boot_delay
                    self.write(self._boot_line(boot[self.boot_index]))
                    self.boot_index += 1
                elif self.boot_timer >= 700:
                    self.complete_boot()
                else:
                    break
        self._update_typing(dt)

        for toast in self.toasts:
            toast[2] -= dt
        self.toasts = [t for t in self.toasts if t[2] > 0]

    @staticmethod
    def _boot_line(text: str):
        for tag, color in (("[ OK ]", "fg"), ("[WARN]", "warn"), ("[FAIL]", "error")):
            if text.startswith(tag):
                return Styled(("[", "dim"), (tag[1:-1], color), ("]", "dim"), (text[len(tag):], None))
        return Styled.plain(text, "title") if text else ""

    # ----------------------------------------------------------- scroll
    def _visible_rows(self) -> int:
        return max(1, self.renderer.char_height - 2)

    def _max_scroll(self) -> int:
        return max(0, len(self.output_lines) - self._visible_rows())

    def _scroll(self, delta: int) -> None:
        self.scroll_offset = max(0, min(self._max_scroll(), self.scroll_offset + delta))

    # ------------------------------------------------------------ render
    def _color(self, c):
        colors = self.renderer.COLORS
        if c is None:
            return colors["fg"]
        if isinstance(c, str):
            return colors.get(c, colors["fg"])
        return c

    def _draw_line(self, x: int, y: int, line) -> None:
        if isinstance(line, Styled):
            for text, color in line.segments:
                self.renderer.write(x, y, text, self._color(color))
                x += len(text)
        else:
            self.renderer.write(x, y, str(line), self._color(None))

    def render(self) -> None:
        r = self.renderer
        r.clear()
        rows = self._visible_rows()
        self.scroll_offset = min(self.scroll_offset, self._max_scroll())
        start = max(0, len(self.output_lines) - rows - self.scroll_offset)
        for i, line in enumerate(self.output_lines[start:start + rows]):
            self._draw_line(1, i, line)

        sep_y, input_y = r.char_height - 2, r.char_height - 1
        r.write(0, sep_y, "─" * r.char_width, r.COLORS["dim"])
        if self.scroll_offset:
            pct = 100 - int(self.scroll_offset * 100 / max(1, self._max_scroll()))
            label = f" scrollback {pct}%  (End to return) "
        elif self.booting:
            label = " press any key "
        else:
            found, total = self.shell.achievements.summary()
            mode = "  GODMODE" if self.shell.practice_mode else ""
            label = f" {found}/{total} achievements{mode} "
        r.write(r.char_width - len(label) - 2, sep_y, label, r.COLORS["dim"])

        if self.showing_intro and not self.is_typing:
            r.write_centered(r.char_height - 4, "[ press any key ]", r.COLORS["menu_normal"])
        if not self.booting and not self.showing_intro:
            x = 0
            for text, color in self.shell.prompt_segments():
                r.write(x, input_y, text, self._color(color))
                x += len(text)
            shown = self.input_buffer
            if self.shell.session and self.shell.session.secret:
                shown = "*" * len(shown)
            room = max(1, r.char_width - x - 1)
            view_start = max(0, self.cursor_pos - room + 1)
            r.write(x, input_y, shown[view_start:view_start + room], r.COLORS["menu_selected"])
            if self.cursor_visible and not self.is_typing:
                under = shown[self.cursor_pos] if self.cursor_pos < len(shown) else " "
                r.write(x + self.cursor_pos - view_start, input_y, under, r.COLORS["bg"],
                        bg=r.COLORS["menu_selected"])

        self._render_toasts()
        r.render()

    def _render_toasts(self) -> None:
        r = self.renderer
        y = 1
        for title, body, remaining in self.toasts[-3:]:
            w = max(len(title), len(body)) + 6
            slide = min(1.0, (TOAST_MS - remaining) / 180.0)
            x = r.char_width - w - 2 + int((1 - slide) * (w + 2))
            bg = (25, 22, 5)
            r.fill_bg(x, y, w, 4, bg)
            r.draw_box(x, y, w, 4, r.COLORS["warn"], style="line")
            r.write(x + 2, y + 1, f"* {title}", r.COLORS["warn"])
            r.write(x + 2, y + 2, body, r.COLORS["accent"])
            y += 5
