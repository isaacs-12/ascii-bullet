"""Static easter-egg commands, generated from ``src/data/easter_eggs.json``."""

from __future__ import annotations

from src.shell.registry import command, load_json
from src.shell.text import Styled

EGGS: dict = load_json("easter_eggs.json")["commands"]


def _make_handler(spec: dict):
    def handler(ctx):
        lines = spec["output"]
        color = spec.get("color")
        if spec.get("typed"):
            ctx.typed(lines, spec.get("delay", 30))
        else:
            ctx.out(*[Styled.plain(x, color) if color and ctx.interactive else x for x in lines])
        if spec.get("achievement"):
            ctx.achieve(spec["achievement"])
        return 0

    return handler


for _name, _spec in EGGS.items():
    command(_name)(_make_handler(_spec))
