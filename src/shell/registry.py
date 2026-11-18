"""
Command registry.

Behaviour lives in Python (``@command`` handlers); everything a player reads
about a command (usage, summary, category, aliases, ``which`` path, man page)
lives in ``src/data/commands.json`` and ``src/data/man_pages.json`` so it can
be shared with other front-ends.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

Handler = Callable[["object"], "int | None"]
_HANDLERS: dict[str, Handler] = {}
_AVAILABILITY: dict[str, Callable[[object], bool]] = {}


@dataclass(frozen=True)
class CommandSpec:
    name: str
    handler: Handler
    category: str = "misc"
    usage: str = ""
    summary: str = ""
    aliases: tuple[str, ...] = ()
    hidden: bool = False
    path: str = ""
    completion: str = "path"  # "path", "dir", "command", "none"
    available: Callable[[object], bool] | None = field(default=None, compare=False)

    def is_available(self, shell) -> bool:
        return self.available is None or bool(self.available(shell))


def command(name: str, available: Callable[[object], bool] | None = None):
    """Register ``fn`` as the handler for ``name`` (metadata comes from JSON)."""

    def decorator(fn: Handler) -> Handler:
        if name in _HANDLERS:
            raise ValueError(f"duplicate handler for {name!r}")
        _HANDLERS[name] = fn
        if available is not None:
            _AVAILABILITY[name] = available
        return fn

    return decorator


@cache
def load_json(name: str):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def registered_handlers() -> dict[str, Handler]:
    return dict(_HANDLERS)


def build_registry() -> dict[str, CommandSpec]:
    """Merge handlers with metadata. Keys include aliases (lower-case)."""
    # Importing the package registers every @command handler.
    from src.shell import commands  # noqa: F401

    meta: dict = load_json("commands.json")
    eggs: dict = load_json("easter_eggs.json")["commands"]
    specs: dict[str, CommandSpec] = {}
    for name, handler in _HANDLERS.items():
        info = meta.get(name)
        if info is None and name in eggs:
            info = {"category": "fun", "hidden": True, "summary": "?", "completion": "none",
                    "aliases": eggs[name].get("aliases", []), "path": f"/usr/games/{name}"}
        info = info or {}
        spec = CommandSpec(
            name=name,
            handler=handler,
            category=info.get("category", "misc"),
            usage=info.get("usage", name),
            summary=info.get("summary", ""),
            aliases=tuple(info.get("aliases", ())),
            hidden=bool(info.get("hidden", False)),
            path=info.get("path", f"/usr/bin/{name}"),
            completion=info.get("completion", "path"),
            available=_AVAILABILITY.get(name),
        )
        specs[name] = spec
        for alias in spec.aliases:
            specs.setdefault(alias, spec)
    return specs
