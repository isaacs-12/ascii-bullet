"""Output line types shared by the shell and the terminal UI."""

from __future__ import annotations

from collections.abc import Iterable

# A colour is either a theme key ("accent", "error", ...) or an RGB tuple.
Color = "str | tuple[int, int, int] | None"


class Styled:
    """A single output line made of coloured segments.

    ``str(styled)`` gives the plain text, which is what pipes and redirects see.
    """

    __slots__ = ("segments",)

    def __init__(self, *segments: tuple[str, object]):
        self.segments: list[tuple[str, object]] = [(str(t), c) for t, c in segments]

    @classmethod
    def plain(cls, text: str, color: object = None) -> Styled:
        return cls((text, color))

    def __str__(self) -> str:
        return "".join(t for t, _ in self.segments)

    def __len__(self) -> int:
        return sum(len(t) for t, _ in self.segments)

    def __eq__(self, other) -> bool:
        return str(self) == str(other)

    def __hash__(self) -> int:
        return hash(str(self))

    def __repr__(self) -> str:
        return f"Styled({str(self)!r})"

    def wrap(self, width: int) -> list[Styled]:
        """Split into lines no wider than ``width`` (hard wrap, keeps colours)."""
        if width <= 0 or len(self) <= width:
            return [self]
        lines: list[Styled] = []
        current: list[tuple[str, object]] = []
        used = 0
        for text, color in self.segments:
            while text:
                room = width - used
                chunk, text = text[:room], text[room:]
                current.append((chunk, color))
                used += len(chunk)
                if used >= width:
                    lines.append(Styled(*current))
                    current, used = [], 0
        if current:
            lines.append(Styled(*current))
        return lines


Line = "str | Styled"


def plain(line) -> str:
    return str(line)


def wrap_line(line, width: int) -> list:
    """Hard-wrap a str or Styled line to ``width`` columns."""
    if isinstance(line, Styled):
        return line.wrap(width)
    text = str(line)
    if width <= 0 or len(text) <= width:
        return [text]
    return [text[i:i + width] for i in range(0, len(text), width)]


def columns(items: Iterable[str], width: int, gap: int = 2) -> list[str]:
    """Lay out ``items`` in ls-style columns that fit ``width``."""
    items = list(items)
    if not items:
        return []
    col_w = max(len(i) for i in items) + gap
    per_row = max(1, width // col_w)
    rows = (len(items) + per_row - 1) // per_row
    out = []
    for r in range(rows):
        row_items = [items[c * rows + r] for c in range(per_row) if c * rows + r < len(items)]
        out.append("".join(i.ljust(col_w) for i in row_items).rstrip())
    return out
