"""
Parody "AI coding assistant" CLIs: claude, gemini, codex, copilot, ollama.

There is no model and no network here. Replies come from keyword rules and
templates in ``src/data/ai_clis.json``; every persona admits it's fake when
asked. The one genuinely useful thing they do is give progress-aware hints.
"""

from __future__ import annotations

import random
import re
from datetime import datetime

from src.shell.registry import command, load_json
from src.shell.shell import InputSession
from src.shell.text import Styled

_DATA = load_json("ai_clis.json")
PERSONAS: dict[str, dict] = _DATA["personas"]
_STOPWORDS = set(
    "a an the and or but if then so to of in on at for with about from by is are was were be been "
    "can could would should will do does did i me my you your it this that what how why who please "
    "help just make some any".split()
)


def _topic(prompt: str) -> str:
    words = [w for w in re.findall(r"[a-zA-Z_][a-zA-Z0-9_.\-]*", prompt.lower()) if w not in _STOPWORDS]
    if not words:
        return "that"
    return max(words, key=len)


def _random_file(fs) -> str:
    items = [i for i in fs.list_directory(show_hidden=False) if not i.endswith("/")]
    return random.choice(items) if items else "README.md"


def _condition_met(shell, cond: str) -> bool:
    negate = cond.startswith("!")
    cond = cond.lstrip("!")
    if cond == "always":
        result = True
    elif cond == "virus":
        result = bool(shell.process_manager.virus_active) and not shell.game.save_system.is_virus_killed()
    elif cond.startswith("achievement:"):
        result = shell.achievements.is_unlocked(cond.split(":", 1)[1])
    else:
        result = False
    return result != negate


def next_hint(shell) -> str:
    for hint in _DATA["hints"]:
        if _condition_met(shell, hint["when"]):
            return hint["text"]
    return "You've done everything I know about. I'm out of if-statements."


class Persona:
    def __init__(self, key: str, shell):
        self.key = key
        self.data = PERSONAS[key]
        self.shell = shell
        self.color = tuple(self.data["color"])

    # ---------------------------------------------------------- rendering
    def styled(self, text: str, color=None) -> Styled:
        return Styled.plain(text, color or self.color)

    def banner(self) -> list:
        cwd = self.shell.cwd_display()
        return [self.styled(line.format(cwd=cwd[:21])) for line in self.data["banner"]]

    def spinner_line(self) -> str:
        word = random.choice(self.data["spinner"])
        return f"{self.data.get('spinner_glyph', '*')} {word}... ({random.randint(1, 9)}s, 0 tokens)"

    # ------------------------------------------------------------- brains
    def _values(self, prompt: str) -> dict:
        """Template slots, computed once per reply so repeated slots agree."""
        n = random.randint(3, 99)
        return {
            "topic": _topic(prompt),
            "file": _random_file(self.shell.fs),
            "n": n,
            "n2": random.randint(1, n),
            "prompt": prompt.rstrip(".?! "),
            "completion": random.choice(self.data.get("completions", ["..."])),
            "hint": next_hint(self.shell),
            "joke": random.choice(_DATA["jokes"]),
            "time": datetime.now().strftime("%H:%M on %A"),
            "greeting": " ".join(self.data.get("greeting", ["Hello."])),
            "display": self.data["display"],
            "display_short": self.data["display_short"],
            "cwd": self.shell.cwd_display(),
        }

    @staticmethod
    def _fill_all(templates: list[str], values: dict) -> list[str]:
        out = []
        for template in templates:
            try:
                out.append(template.format(**values))
            except (KeyError, IndexError, ValueError):
                out.append(template)
        return out

    def respond(self, prompt: str) -> tuple[list[str], str | None]:
        """Return (reply lines, achievement id or None)."""
        text = prompt.strip()
        lowered = f" {text.lower()} "
        if text.startswith("/"):
            cmd = text.split()[0].lower()
            slash = self.data.get("slash", {})
            if cmd in slash:
                return self._fill_all(slash[cmd], self._values(text)), None
            return [f"Unknown command {cmd}. Try /help."], None
        for rule in self.data.get("rules", []) + _DATA["common_rules"]:
            if any(m in lowered for m in rule["match"]):
                return self._fill_all(rule["reply"], self._values(text)), rule.get("achievement")
        return self._fill_all(random.choice(self.data["fallback"]), self._values(text)), None

    def answer(self, prompt: str, interactive: bool) -> list:
        lines, achievement = self.respond(prompt)
        if achievement:
            self.shell.achievements.unlock(achievement)
        save = self.shell.game.save_system
        save.update_stat("ai_prompts", 1)
        out = []
        if interactive:
            out.append(Styled.plain(self.spinner_line(), "dim"))
        out.extend(self.styled(line) if i == 0 else line for i, line in enumerate(lines))
        return out


def _track_usage(ctx, key: str) -> None:
    save = ctx.save
    used = set(save.get_flag("ai_used", []))
    if key not in used:
        used.add(key)
        save.set_flag("ai_used", sorted(used))
    ctx.achieve("ai_curious")
    if used >= set(PERSONAS):
        ctx.achieve("ai_whisperer")


def _make_handler(key: str):
    def handler(ctx):
        persona = Persona(key, ctx.shell)
        data = persona.data
        args = list(ctx.args)
        if args and args[0] in ("--version", "-v", "version"):
            ctx.out(f"{data['display']} {data['version']} (parody; not the real {data['display_short']})")
            return 0
        if args and args[0] in ("--help", "-h"):
            ctx.out(f"Usage: {key} [prompt]      start a chat, or ask one question",
                    f"       {key} -p <prompt>    print a single answer and exit",
                    f"       <cmd> | {key}        use piped text as the prompt",
                    "",
                    f"{data['display']} is a parody that runs on if-statements. No API key, no network.")
            return 0
        if args and args[0].startswith("--dangerously"):
            ctx.out(persona.styled("Permissions skipped. There was nothing to permit. I'm a lookup table."))
            args = args[1:]
        if args and args[0] in ("-p", "--print"):
            args = args[1:]
        _track_usage(ctx, key)

        prompt = " ".join(args).strip()
        if ctx.stdin is not None:
            piped = " ".join(ctx.input_lines()).strip()
            prompt = f"{prompt} {piped}".strip()

        if prompt:
            reply = persona.answer(prompt, ctx.interactive)
            if ctx.interactive:
                ctx.typed(reply, delay=6)
            else:
                ctx.out(*[str(x) for x in reply if not str(x).startswith(data.get("spinner_glyph", "*") + " ")])
            return 0

        if not ctx.interactive:
            ctx.err(f"{key}: no prompt given (stdin was empty)")
            return 1

        shell = ctx.shell
        ctx.out(*persona.banner(), "")
        greeting = data.get("greeting")
        if greeting:
            ctx.out(persona.styled(greeting[0]), *greeting[1:])

        def on_line(line: str) -> bool:
            stripped = line.strip()
            if stripped.lower() in _DATA["exit_words"]:
                shell.ui.write(Styled.plain(f"({data['display']} session ended. Nothing was sent anywhere.)", "dim"))
                return False
            if not stripped:
                return True
            if stripped == "/clear":
                shell.ui.clear()
                return True
            shell.ui.typed(persona.answer(stripped, True) + [""], 6)
            return True

        def complete(buffer: str) -> list[str]:
            return [c for c in list(data.get("slash", {})) + ["/exit"] if c.startswith(buffer)]

        ctx.start_session(InputSession(
            prompt=[(data["prompt"], persona.color)],
            on_line=on_line,
            on_cancel=lambda: shell.ui.write(Styled.plain("^C (session ended)", "dim")),
            complete=complete,
        ))
        return 0

    handler.__name__ = f"ai_{key}"
    return handler


for _key in PERSONAS:
    command(_key)(_make_handler(_key))


@command("ai")
def ai_list(ctx):
    ctx.out(Styled.plain("Walnut AI Division - assistant directory (all parodies, all offline)", "title"))
    for key, data in PERSONAS.items():
        ctx.out(Styled(("  " + key.ljust(10), tuple(data["color"])), (data["display"], None)))
    ctx.out(Styled.plain("Ask any of them for a hint if you're stuck.", "dim"))
