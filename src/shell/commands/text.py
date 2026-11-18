"""Text-processing commands that make pipes worth having."""

from __future__ import annotations

import base64
import binascii
import codecs
import colorsys
import random

from src.shell.commands.files import _split_flags
from src.shell.registry import command, load_json
from src.shell.text import Styled


@command("echo")
def echo(ctx):
    args = list(ctx.args)
    newline = True
    interpret = False
    while args and args[0] in ("-n", "-e", "-ne", "-en"):
        flag = args.pop(0)
        newline = newline and "n" not in flag
        interpret = interpret or "e" in flag
    text = " ".join(args)
    if interpret:
        text = codecs.decode(text, "unicode_escape")
    ctx.out(text)


@command("sort")
def sort(ctx):
    flags, paths, bad = _split_flags(ctx.args, "rnuf")
    if bad:
        ctx.err(f"sort: invalid option -- '{bad}'")
        return 2
    lines, status = ctx.read_inputs(paths)

    def key(line: str):
        if "n" in flags:
            num = line.strip().split(" ")[0]
            try:
                return (0, float(num), line)
            except ValueError:
                return (1, 0.0, line)
        return (0, 0.0, line.lower() if "f" in flags else line)

    lines = sorted(lines, key=key, reverse="r" in flags)
    if "u" in flags:
        lines = list(dict.fromkeys(lines))
    ctx.out(*lines)
    return status


@command("uniq")
def uniq(ctx):
    flags, paths, _ = _split_flags(ctx.args, "cdu")
    lines, status = ctx.read_inputs(paths)
    groups: list[list] = []
    for line in lines:
        if groups and groups[-1][0] == line:
            groups[-1][1] += 1
        else:
            groups.append([line, 1])
    for line, count in groups:
        if "d" in flags and count < 2:
            continue
        if "u" in flags and count > 1:
            continue
        ctx.out(f"{count:7} {line}" if "c" in flags else line)
    return status


@command("rev")
def rev(ctx):
    lines, status = ctx.read_inputs(ctx.args)
    ctx.out(*[line[::-1] for line in lines])
    return status


def _expand_tr_set(spec: str) -> str:
    out = []
    i = 0
    while i < len(spec):
        if i + 2 < len(spec) and spec[i + 1] == "-":
            start, end = ord(spec[i]), ord(spec[i + 2])
            out.extend(chr(c) for c in range(start, end + 1))
            i += 3
        else:
            out.append(spec[i])
            i += 1
    return "".join(out)


@command("tr")
def tr(ctx):
    flags, operands, _ = _split_flags(ctx.args, "d")
    if not operands or ("d" not in flags and len(operands) < 2):
        ctx.err("tr: missing operand", "Usage: tr <set1> <set2>  |  tr -d <set>")
        return 1
    set1 = _expand_tr_set(operands[0])
    lines = ctx.input_lines()
    if "d" in flags:
        table = str.maketrans("", "", set1)
    else:
        set2 = _expand_tr_set(operands[1])
        set2 = (set2 + set2[-1:] * len(set1))[: len(set1)] if set2 else set1
        table = str.maketrans(set1, set2)
    out = [line.translate(table) for line in lines]
    ctx.out(*out)
    _check_decoded(ctx, out)


@command("rot13")
def rot13(ctx):
    lines, status = ctx.read_inputs(ctx.args)
    out = [codecs.encode(line, "rot13") for line in lines]
    ctx.out(*out)
    _check_decoded(ctx, out)
    return status


@command("base64")
def b64(ctx):
    flags, paths, _ = _split_flags(ctx.args, "d")
    lines, status = ctx.read_inputs(paths)
    if "d" in flags:
        try:
            decoded = base64.b64decode("".join(line.strip() for line in lines), validate=False)
            text = decoded.decode("utf-8", errors="replace")
        except (binascii.Error, ValueError):
            ctx.err("base64: invalid input")
            return 1
        out = text.split("\n")
        ctx.out(*out)
        _check_decoded(ctx, out)
    else:
        encoded = base64.b64encode("\n".join(lines).encode()).decode()
        ctx.out(*[encoded[i:i + 64] for i in range(0, len(encoded), 64)] or [""])
    return status


def _check_decoded(ctx, lines: list[str]) -> None:
    text = "\n".join(lines).lower()
    if "godmode" in text and "intercepted" in text:
        ctx.achieve("codebreaker")
    if "sudo password" in text:
        ctx.achieve("rot13")


@command("cut")
def cut(ctx):
    delim = "\t"
    fields: list[int] = []
    chars: tuple[int, int] | None = None
    paths: list[str] = []
    args = ctx.args
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("-d"):
            delim = a[2:] or (args[i + 1] if i + 1 < len(args) else "\t")
            i += 1 if a[2:] else 2
            continue
        if a.startswith("-f"):
            spec = a[2:] or (args[i + 1] if i + 1 < len(args) else "1")
            fields = [int(x) for x in spec.split(",") if x.isdigit()]
            i += 1 if a[2:] else 2
            continue
        if a.startswith("-c"):
            spec = a[2:] or (args[i + 1] if i + 1 < len(args) else "1")
            lo, _, hi = spec.partition("-")
            chars = (int(lo or 1), int(hi) if hi else 10**6)
            i += 1 if a[2:] else 2
            continue
        paths.append(a)
        i += 1
    lines, status = ctx.read_inputs(paths)
    for line in lines:
        if chars:
            ctx.out(line[chars[0] - 1: chars[1]])
        elif fields:
            parts = line.split(delim)
            ctx.out(delim.join(parts[f - 1] for f in fields if 0 < f <= len(parts)))
        else:
            ctx.out(line)
    return status


@command("nl")
def nl(ctx):
    lines, status = ctx.read_inputs(ctx.args)
    ctx.out(*[f"{i:6}\t{line}" for i, line in enumerate(lines, 1)])
    return status


@command("tee")
def tee(ctx):
    append = "-a" in ctx.args
    paths = [a for a in ctx.args if a != "-a"]
    lines = ctx.input_lines()
    for p in paths:
        ctx.shell._write_file(p, list(lines), append, ctx)
    ctx.out(*lines)


@command("seq")
def seq(ctx):
    try:
        nums = [int(a) for a in ctx.args]
    except ValueError:
        ctx.err("seq: invalid number")
        return 1
    if not nums:
        ctx.err("seq: missing operand")
        return 1
    start, step, end = (1, 1, nums[0]) if len(nums) == 1 else (
        (nums[0], 1, nums[1]) if len(nums) == 2 else (nums[0], nums[1], nums[2]))
    if step == 0:
        ctx.err("seq: step can't be zero")
        return 1
    values = range(start, end + (1 if step > 0 else -1), step)
    ctx.out(*[str(v) for v in list(values)[:5000]])


@command("yes")
def yes(ctx):
    word = " ".join(ctx.args) or "y"
    ctx.out(*[word] * 200)
    if ctx.interactive:
        ctx.out(Styled.plain("^C  (yes: stopped after 200 lines to save your scrollback)", "dim"))


# --------------------------------------------------------------- fun text

@command("fortune")
def fortune(ctx):
    ok, lines = ctx.read("/usr/share/games/fortunes", track=False)
    if not ok or not lines:
        ctx.err("fortune: no fortunes found (did someone delete /usr/share/games/fortunes?)")
        return 1
    ctx.out(random.choice([x for x in lines if x.strip()]))


def _bubble(lines: list[str], width: int = 40) -> list[str]:
    import textwrap

    wrapped: list[str] = []
    for line in lines or [""]:
        wrapped.extend(textwrap.wrap(line, width) or [""])
    w = max(len(x) for x in wrapped)
    out = [" " + "_" * (w + 2)]
    if len(wrapped) == 1:
        out.append(f"< {wrapped[0].ljust(w)} >")
    else:
        for i, line in enumerate(wrapped):
            left, right = ("/", "\\") if i == 0 else (("\\", "/") if i == len(wrapped) - 1 else ("|", "|"))
            out.append(f"{left} {line.ljust(w)} {right}")
    out.append(" " + "-" * (w + 2))
    return out


@command("cowsay")
def cowsay(ctx):
    text = [" ".join(ctx.args)] if ctx.args else ctx.input_lines()
    if not text or not any(t.strip() for t in text):
        text = ["Moo. (try: fortune | cowsay)"]
    cows = load_json("art.json")["cows"]
    cow = cows["wally"] if any("wally" in t.lower() for t in text) else cows["default"]
    ctx.out(*_bubble(text), *cow)


@command("figlet")
def figlet(ctx):
    text = " ".join(ctx.args) if ctx.args else " ".join(ctx.input_lines())
    if not text:
        ctx.err("Usage: figlet <text>")
        return 1
    font = load_json("art.json")["block_font"]
    height = len(font["A"])
    rows = ["" for _ in range(height)]
    for ch in text.upper()[:24]:
        glyph = font.get(ch, font["?"])
        for r in range(height):
            rows[r] += glyph[r] + " "
    ctx.out(*[r.rstrip() for r in rows])


def rainbow(line: str, offset: float) -> Styled:
    segments = []
    for i, ch in enumerate(line):
        r, g, b = colorsys.hsv_to_rgb(((i * 0.03) + offset) % 1.0, 0.75, 1.0)
        segments.append((ch, (int(r * 255), int(g * 255), int(b * 255))))
    return Styled(*segments)


@command("lolcat")
def lolcat(ctx):
    lines, status = ctx.read_inputs(ctx.args)
    if not ctx.interactive:
        ctx.out(*lines)
        return status
    base = random.random()
    for i, line in enumerate(lines):
        ctx.out(rainbow(line, base + i * 0.05))
    return status
