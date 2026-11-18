"""
A small POSIX-ish command line parser.

Supported: single/double quotes, backslash escapes, ``$VAR`` / ``${VAR}`` /
``$?`` expansion, ``~`` expansion, globbing (``*``, ``?``, ``[...]``) via a
callback, pipes ``|``, redirects ``>`` ``>>`` ``<`` ``2>`` ``2>>``, and
command lists joined by ``&&``, ``||`` and ``;``.

Not supported (on purpose): subshells, functions, backgrounding, heredocs.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

OPERATORS = ("&&", "||", ">>", "2>>", "2>", "|", ";", ">", "<")
_VAR_RE = re.compile(r"\$(\?|[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})")


class ParseError(Exception):
    """Raised for unterminated quotes or dangling operators."""


@dataclass
class Word:
    text: str
    globbable: bool = False  # contains unquoted glob characters


@dataclass
class Redirect:
    kind: str  # '>', '>>', '<', '2>', '2>>'
    target: str


@dataclass
class SimpleCommand:
    argv: list[str] = field(default_factory=list)
    redirects: list[Redirect] = field(default_factory=list)


@dataclass
class Pipeline:
    commands: list[SimpleCommand] = field(default_factory=list)


@dataclass
class CommandList:
    """A sequence of pipelines; ``ops[i]`` joins pipelines[i] to pipelines[i+1]."""

    pipelines: list[Pipeline] = field(default_factory=list)
    ops: list[str] = field(default_factory=list)


def _expand_vars(text: str, env: Mapping[str, str]) -> str:
    def repl(m: re.Match) -> str:
        name = m.group(1).strip("{}")
        return str(env.get(name, ""))

    return _VAR_RE.sub(repl, text)


def tokenize(line: str, env: Mapping[str, str] | None = None, home: str = "~") -> list[object]:
    """Split ``line`` into Word and operator (str) tokens, expanding variables."""
    env = env or {}
    tokens: list[object] = []
    buf: list[str] = []
    globbable = False
    in_word = False
    i, n = 0, len(line)

    def flush() -> None:
        nonlocal buf, globbable, in_word
        if in_word:
            tokens.append(Word("".join(buf), globbable))
        buf, globbable, in_word = [], False, False

    while i < n:
        ch = line[i]
        if ch in " \t":
            flush()
            i += 1
            continue
        op = next((o for o in sorted(OPERATORS, key=len, reverse=True) if line.startswith(o, i)), None)
        # "2>" only counts as an operator at the start of a word.
        if op and op.startswith("2") and in_word:
            op = None
        if op:
            flush()
            tokens.append(op)
            i += len(op)
            continue
        if ch == "'":
            end = line.find("'", i + 1)
            if end == -1:
                raise ParseError("unterminated single quote")
            buf.append(line[i + 1:end])
            in_word = True
            i = end + 1
            continue
        if ch == '"':
            j = i + 1
            chunk: list[str] = []
            while j < n and line[j] != '"':
                if line[j] == "\\" and j + 1 < n and line[j + 1] in '"\\$`':
                    chunk.append(line[j + 1])
                    j += 2
                    continue
                chunk.append(line[j])
                j += 1
            if j >= n:
                raise ParseError("unterminated double quote")
            buf.append(_expand_vars("".join(chunk), env))
            in_word = True
            i = j + 1
            continue
        if ch == "\\" and i + 1 < n:
            buf.append(line[i + 1])
            in_word = True
            i += 2
            continue
        if ch == "~" and not in_word and (i + 1 == n or line[i + 1] in "/ \t"):
            buf.append(home)
            in_word = True
            i += 1
            continue
        if ch == "$":
            m = _VAR_RE.match(line, i)
            if m:
                buf.append(_expand_vars(m.group(0), env))
                in_word = True
                i = m.end()
                continue
        if ch in "*?[":
            globbable = True
        buf.append(ch)
        in_word = True
        i += 1
    flush()
    return tokens


def parse(
    line: str,
    env: Mapping[str, str] | None = None,
    home: str = "~",
    glob: Callable[[str], list[str]] | None = None,
) -> CommandList:
    """Parse a full command line into a CommandList."""
    tokens = tokenize(line, env, home)
    result = CommandList()
    pipeline = Pipeline()
    cmd = SimpleCommand()
    i = 0

    def end_command() -> None:
        nonlocal cmd
        if not cmd.argv and not cmd.redirects:
            raise ParseError("syntax error near unexpected token")
        pipeline.commands.append(cmd)
        cmd = SimpleCommand()

    while i < len(tokens):
        tok = tokens[i]
        if isinstance(tok, Word):
            if tok.globbable and glob:
                matches = glob(tok.text)
                cmd.argv.extend(matches or [tok.text])
            else:
                cmd.argv.append(tok.text)
        elif tok in (">", ">>", "<", "2>", "2>>"):
            if i + 1 >= len(tokens) or not isinstance(tokens[i + 1], Word):
                raise ParseError(f"syntax error near unexpected token `{tok}'")
            cmd.redirects.append(Redirect(tok, tokens[i + 1].text))
            i += 1
        elif tok == "|":
            end_command()
        elif tok in ("&&", "||", ";"):
            if cmd.argv or cmd.redirects:
                end_command()
            if not pipeline.commands:
                if tok == ";" and not result.pipelines:
                    i += 1
                    continue
                raise ParseError(f"syntax error near unexpected token `{tok}'")
            result.pipelines.append(pipeline)
            result.ops.append(tok)
            pipeline = Pipeline()
        i += 1

    if cmd.argv or cmd.redirects:
        end_command()
    elif pipeline.commands is not None and tokens and tokens[-1] == "|":
        raise ParseError("syntax error: unexpected end of input after `|'")
    if pipeline.commands:
        result.pipelines.append(pipeline)
    elif result.ops and result.ops[-1] == ";":
        result.ops.pop()
    elif result.ops:
        raise ParseError(f"syntax error: unexpected end of input after `{result.ops[-1]}'")
    return result
