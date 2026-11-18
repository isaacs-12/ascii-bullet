"""
The BLTHLL shell: parses a command line and runs it against the registry.

The shell is UI-agnostic. A front-end (the main terminal, the editor's
embedded terminal, tests) implements the small ``ShellUI`` protocol and calls
``Shell.submit(line)``.
"""

from __future__ import annotations

import difflib
import fnmatch
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Protocol

from src.core.achievements import AchievementTracker
from src.core.puzzle_system import check_puzzles
from src.shell.parser import ParseError, Redirect, parse
from src.shell.registry import CommandSpec, build_registry, load_json
from src.shell.text import Styled, wrap_line

HOME = "/home/pilot/blthll"
SUDO_PASSWORD = "WallySmith"
SUDO_TTL_SECONDS = 300
MAX_PIPELINE_LINES = 5000


class ShellUI(Protocol):
    """What the shell needs from whatever is displaying it."""

    width: int

    def write(self, line) -> None: ...
    def typed(self, lines: list, delay: int = 30) -> None: ...
    def clear(self) -> None: ...
    def launch(self, factory: Callable) -> None: ...
    def quit(self) -> None: ...
    def notify(self, title: str, body: str) -> None: ...


@dataclass
class InputSession:
    """Takes over the prompt (sudo password, AI chat, yes/no questions)."""

    prompt: object  # str or list of (text, color) segments
    on_line: Callable[[str], bool]  # return True to keep the session open
    secret: bool = False
    on_cancel: Callable[[], None] | None = None
    complete: Callable[[str], list[str]] | None = None


class ExecContext:
    """Everything a command handler gets: args, stdin, and output helpers."""

    def __init__(self, shell: Shell, argv: list[str], stdin: list[str] | None, interactive: bool):
        self.shell = shell
        self.argv = argv
        self.name = argv[0]
        self.args = argv[1:]
        self.stdin = stdin
        self.stdout: list = []
        self.stderr: list = []
        self.interactive = interactive  # stdout goes straight to the terminal

    # ---------------------------------------------------------- shortcuts
    @property
    def fs(self):
        return self.shell.fs

    @property
    def game(self):
        return self.shell.game

    @property
    def save(self):
        return self.shell.game.save_system

    @property
    def width(self) -> int:
        return self.shell.ui.width

    # ------------------------------------------------------------ output
    def out(self, *lines) -> None:
        for line in lines:
            if isinstance(line, Styled):
                self.stdout.append(line)
            else:
                self.stdout.extend(str(line).split("\n"))

    def err(self, *lines) -> None:
        for line in lines:
            self.stderr.append(line if isinstance(line, Styled) else Styled.plain(str(line), "error"))

    def typed(self, lines: list, delay: int = 30) -> None:
        """Animated output when shown in the terminal; plain text when piped."""
        if self.interactive:
            self.shell.flush_pending(self)
            self.shell.ui.typed(list(lines), delay)
        else:
            self.out(*lines)

    def input_lines(self) -> list[str]:
        return [str(line) for line in (self.stdin or [])]

    # ------------------------------------------------------------ effects
    def launch(self, factory: Callable) -> None:
        """Switch to a full-screen state after this command line finishes."""
        if self.interactive:
            self.shell.pending_launch = factory

    def achieve(self, achievement_id: str) -> None:
        self.shell.achievements.unlock(achievement_id)

    def start_session(self, session: InputSession) -> None:
        self.shell.session = session

    def read(self, path: str, track: bool = True):
        """Read a file by path. Returns (ok, lines | error) and records exploration."""
        if path == "/dev/null":
            return True, []
        if self.fs.is_directory_path(path):
            return False, f"{path}: Is a directory"
        if not self.fs.file_exists(path):
            return False, f"{path}: No such file or directory"
        ok, content = self.fs.read_file(path)
        if not ok:
            return False, f"{path}: Permission denied"
        if track:
            abspath = self.fs.abspath(path)
            self.save.mark_file_read(abspath)
            self.shell.achievements.on_read(abspath)
        return True, [str(line) for line in content]

    def read_inputs(self, paths: list[str]) -> tuple[list[str], int]:
        """Concatenate files (or stdin when no paths / '-'). Returns (lines, status)."""
        if not paths:
            return self.input_lines(), 0
        lines: list[str] = []
        status = 0
        for p in paths:
            if p == "-":
                lines.extend(self.input_lines())
                continue
            ok, content = self.read(p)
            if ok:
                lines.extend(content)
            else:
                self.err(f"{self.name}: {content}")
                status = 1
        return lines, status


class Shell:
    def __init__(self, game, fs, process_manager, systemd_manager, ui: ShellUI):
        self.game = game
        self.fs = fs
        self.process_manager = process_manager
        self.systemd = systemd_manager
        self.ui = ui
        self.registry: dict[str, CommandSpec] = build_registry()
        self.easter = load_json("easter_eggs.json")
        self.achievements = AchievementTracker(game.save_system, self._on_achievement)
        self.env: dict[str, str] = {
            "USER": "pilot", "LOGNAME": "pilot", "HOME": HOME, "SHELL": "/bin/blsh",
            "PATH": "/usr/local/bin:/usr/bin:/bin:/opt/walnut/ai/bin", "TERM": "xterm-256color",
            "LANG": "en_US.UTF-8", "HOSTNAME": "blthll", "EDITOR": "vim",
            "BLTHLL_VERSION": "0.2.0", "API_KEY": "(none needed. that's the joke.)",
        }
        self.aliases: dict[str, str] = {"ll": "ls -la", "la": "ls -a", "cls": "clear", "..": "cd .."}
        self.history: list[str] = list(game.save_system.get_command_history())
        self.last_status = 0
        self.sudo_until = 0.0
        self.session: InputSession | None = None
        self.pending_launch: Callable | None = None
        self.practice_mode = False
        self._root_depth = 0

    # ------------------------------------------------------------ prompt
    @property
    def user(self) -> str:
        return self.fs.get_current_user()

    def cwd_display(self) -> str:
        pwd = self.fs.get_pwd()
        if pwd == HOME or pwd.startswith(HOME + "/"):
            return "~" + pwd[len(HOME):]
        return pwd

    def prompt_segments(self) -> list[tuple[str, object]]:
        if self.session:
            p = self.session.prompt
            return [(p, "accent")] if isinstance(p, str) else list(p)
        sigil = "#" if self.user == "root" else "$"
        user_color = "error" if self.user == "root" else "accent"
        return [(f"{self.user}@blthll", user_color), (":", "dim"), (self.cwd_display(), "fg"), (f"{sigil} ", "dim")]

    def prompt_text(self) -> str:
        return "".join(t for t, _ in self.prompt_segments())

    # ------------------------------------------------------------- entry
    def submit(self, line: str) -> None:
        """Handle one line typed at the prompt."""
        if self.session:
            session = self.session
            keep = session.on_line(line)
            if not keep and self.session is session:
                self.session = None
            self._after_line()
            return
        self.run(line)

    def cancel_session(self) -> None:
        if self.session:
            cb = self.session.on_cancel
            self.session = None
            if cb:
                cb()

    def record_history(self, line: str) -> None:
        if line and (not self.history or self.history[-1] != line):
            self.history.append(line)
        if len(self.history) % 10 == 0:
            self.game.save_system.save_command_history(self.history)

    def run(self, line: str, record: bool = True) -> int:
        line = line.strip()
        if not line:
            return self.last_status
        if "!!" in line:
            if not self.history:
                self.ui.write(Styled.plain("blsh: !!: event not found", "error"))
                return 1
            line = line.replace("!!", self.history[-1])
            self.ui.write(line)
        if record:
            self.record_history(line)

        if self._easter_phrase(line):
            self._after_line()
            return 0

        try:
            cmdlist = parse(line, self._env_view(), HOME, self._glob)
        except ParseError as e:
            self.ui.write(Styled.plain(f"blsh: {e}", "error"))
            self.last_status = 2
            return 2

        status = 0
        for idx, pipeline in enumerate(cmdlist.pipelines):
            if idx > 0:
                op = cmdlist.ops[idx - 1]
                if (op == "&&" and status != 0) or (op == "||" and status == 0):
                    continue
            status = self._run_pipeline(pipeline)
            self.last_status = status
        self._after_line()
        return status

    # --------------------------------------------------------- execution
    def _env_view(self) -> dict:
        view = dict(self.env)
        view["PWD"] = self.fs.get_pwd()
        view["USER"] = self.user
        view["?"] = str(self.last_status)
        return view

    def _glob(self, pattern: str) -> list[str]:
        directory, _, base = pattern.rpartition("/")
        list_dir = directory if directory else "."
        if pattern.startswith("/") and not directory:
            list_dir = "/"
        if any(c in directory for c in "*?["):
            return []
        ok, items = self.fs.list_directory_at_path(list_dir or "/", show_hidden=base.startswith("."))
        if not ok:
            return []
        names = [i.rstrip("/") for i in items]
        prefix = (directory + "/") if directory else ""
        if pattern.startswith("/") and not directory:
            prefix = "/"
        return sorted(prefix + n for n in names if fnmatch.fnmatchcase(n, base))

    def resolve(self, name: str) -> CommandSpec | None:
        spec = self.registry.get(name) or self.registry.get(name.lower())
        if spec and spec.is_available(self):
            return spec
        return None

    def _expand_alias(self, argv: list[str]) -> list[str]:
        alias = self.aliases.get(argv[0])
        if alias:
            return alias.split() + argv[1:]
        return argv

    def _run_pipeline(self, pipeline) -> int:
        stdin: list | None = None
        status = 0
        last = len(pipeline.commands) - 1
        if last >= 2:
            self.achievements.unlock("pipe_dream")
        for i, cmd in enumerate(pipeline.commands):
            argv = self._expand_alias(cmd.argv) if cmd.argv else cmd.argv
            redirect_out = any(r.kind in (">", ">>") for r in cmd.redirects)
            interactive = i == last and not redirect_out
            for r in cmd.redirects:
                if r.kind == "<":
                    ok, lines = ExecContext(self, ["<"], None, False).read(r.target)
                    if not ok:
                        self.ui.write(Styled.plain(f"blsh: {lines}", "error"))
                        return 1
                    stdin = lines
            if not argv:
                ctx = ExecContext(self, [""], stdin, interactive)
            else:
                ctx = ExecContext(self, argv, stdin, interactive)
                status = self._invoke(ctx)
            self._apply_output_redirects(ctx, cmd.redirects)
            stdin = [str(line) for line in ctx.stdout][:MAX_PIPELINE_LINES]
        if self.pending_launch is not None:
            factory, self.pending_launch = self.pending_launch, None
            self.ui.launch(factory)
        return status

    def _invoke(self, ctx: ExecContext) -> int:
        spec = self.resolve(ctx.name)
        if spec is None:
            ctx.err(f"blsh: {ctx.name}: command not found")
            visible = [n for n, s in self.registry.items() if not s.hidden and s.is_available(self)]
            guess = difflib.get_close_matches(ctx.name.lower(), visible, n=1, cutoff=0.75)
            if guess:
                ctx.err(Styled.plain(f"  did you mean '{guess[0]}'?", "dim"))
            return 127
        try:
            result = spec.handler(ctx)
        except Exception as e:  # noqa: BLE001 - a buggy command must not kill the terminal
            ctx.err(f"{ctx.name}: internal error: {type(e).__name__}: {e}")
            return 1
        status = 0 if result is None else int(result)
        if status == 0:
            self.achievements.on_command(spec.name, ctx.args)
        return status

    def _apply_output_redirects(self, ctx: ExecContext, redirects: list[Redirect]) -> None:
        stdout_target = None
        for r in redirects:
            if r.kind in (">", ">>"):
                stdout_target = r
            elif r.kind in ("2>", "2>>"):
                if r.target != "/dev/null":
                    self._write_file(r.target, [str(x) for x in ctx.stderr], r.kind == "2>>", ctx)
                ctx.stderr = []
        for line in ctx.stderr:
            self.ui.write(line)
        ctx.stderr = []
        if stdout_target is not None:
            if stdout_target.target != "/dev/null":
                self._write_file(stdout_target.target, [str(x) for x in ctx.stdout],
                                 stdout_target.kind == ">>", ctx)
            ctx.stdout = []
        elif ctx.interactive:
            self.flush_pending(ctx)

    def flush_pending(self, ctx: ExecContext) -> None:
        for line in ctx.stdout:
            self.ui.write(line)
        ctx.stdout = []
        for line in ctx.stderr:
            self.ui.write(line)
        ctx.stderr = []

    def _write_file(self, path: str, lines: list[str], append: bool, ctx: ExecContext) -> bool:
        fs = self.fs
        if fs.is_directory_path(path):
            self.ui.write(Styled.plain(f"blsh: {path}: Is a directory", "error"))
            return False
        if not fs.file_exists(path):
            ok, error = fs.create_file(path, lines)
        else:
            if append:
                ok_read, existing = fs.read_file(path)
                lines = (list(existing) if ok_read else []) + lines
            ok, error = fs.write_file(path, lines, append=False)
        if not ok:
            self.ui.write(Styled.plain(f"blsh: {error}", "error"))
            return False
        self.save_filesystem()
        return True

    # ------------------------------------------------------------ helpers
    def save_filesystem(self) -> None:
        self.game.save_system.save_filesystem(self.fs.get_state())

    @contextmanager
    def as_root(self):
        previous = self.fs.get_current_user()
        self.fs.set_user("root")
        self._root_depth += 1
        try:
            yield
        finally:
            self._root_depth -= 1
            self.fs.set_user(previous)

    def sudo_valid(self) -> bool:
        return time.monotonic() < self.sudo_until

    def grant_sudo(self) -> None:
        self.sudo_until = time.monotonic() + SUDO_TTL_SECONDS

    def _easter_phrase(self, line: str) -> bool:
        key = " ".join(line.lower().split())
        egg = self.easter.get("phrases", {}).get(key)
        if not egg:
            return False
        lines = egg.get("output", [])
        color = egg.get("color")
        if egg.get("typed"):
            self.ui.typed(lines, egg.get("delay", 30))
        else:
            for text in lines:
                self.ui.write(Styled.plain(text, color) if color else text)
        if egg.get("achievement"):
            self.achievements.unlock(egg["achievement"])
        self.last_status = 0
        return True

    def _after_line(self) -> None:
        for trigger in ("rm", "chmod", "systemctl"):
            for _game, message in check_puzzles(self.fs, self.game.save_system, trigger):
                self.ui.write("")
                self.ui.write(Styled.plain("*" * min(60, self.ui.width - 2), "warn"))
                self.ui.write(Styled.plain(message, "warn"))
                self.ui.write(Styled.plain("*" * min(60, self.ui.width - 2), "warn"))
                self.achievements.unlock(f"unlock_{_game}")

    def _on_achievement(self, achievement: dict) -> None:
        self.ui.notify("ACHIEVEMENT UNLOCKED", achievement["name"])

    def write_wrapped(self, line) -> list:
        return wrap_line(line, self.ui.width)

    # -------------------------------------------------------- completion
    def complete(self, buffer: str) -> tuple[str, list[str]]:
        """Tab-complete the last word. Returns (new_buffer, candidates_to_show)."""
        if self.session:
            if self.session.complete:
                options = self.session.complete(buffer)
                return self._apply_completion(buffer, buffer, options, add_space=True)
            return buffer, []
        words = buffer.split(" ")
        current = words[-1]
        if len(words) == 1:
            names = sorted({n for n, s in self.registry.items() if not s.hidden and s.is_available(self)}
                           | set(self.aliases))
            options = [n for n in names if n.startswith(current)]
            return self._apply_completion(buffer, current, options, add_space=True)

        spec = self.resolve(words[0])
        mode = spec.completion if spec else "path"
        if mode == "none":
            return buffer, []
        if mode == "command":
            names = sorted(n for n, s in self.registry.items() if not s.hidden)
            return self._apply_completion(buffer, current, [n for n in names if n.startswith(current)], True)
        return self._complete_path(buffer, current, dirs_only=(mode == "dir"))

    def _complete_path(self, buffer: str, current: str, dirs_only: bool) -> tuple[str, list[str]]:
        directory, slash, base = current.rpartition("/")
        list_dir = (directory or "/") if slash else "."
        display_prefix = directory + slash
        expanded = list_dir
        if list_dir == "~" or list_dir.startswith("~/"):
            expanded = HOME + list_dir[1:]
        ok, items = self.fs.list_directory_at_path(expanded, show_hidden=base.startswith("."))
        if not ok:
            return buffer, []
        options = []
        for item in items:
            is_dir = item.endswith("/")
            if dirs_only and not is_dir:
                continue
            if item.rstrip("/").startswith(base):
                options.append(display_prefix + item)
        if not dirs_only and ".." .startswith(base) and base.startswith("."):
            options.append(display_prefix + "../")
        return self._apply_completion(buffer, current, sorted(set(options)), add_space=False)

    @staticmethod
    def _apply_completion(buffer: str, current: str, options: list[str], add_space: bool):
        if not options:
            return buffer, []
        head = buffer[: len(buffer) - len(current)]
        if len(options) == 1:
            choice = options[0]
            return head + choice + ("" if choice.endswith("/") else " "), []
        prefix = options[0]
        for o in options[1:]:
            while not o.startswith(prefix):
                prefix = prefix[:-1]
        shown = [o.rstrip("/").rsplit("/", 1)[-1] + ("/" if o.endswith("/") else "") for o in options]
        return head + prefix, shown
