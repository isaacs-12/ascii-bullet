"""
A small POSIX-ish command line parser.

Supported: single/double quotes, backslash escapes, ``$VAR`` / ``${VAR}`` /
``$?`` expansion, ``~`` expansion, globbing (``*``, ``?``, ``[...]``) via a
callback, pipes ``|``, redirects ``>`` ``>>`` ``<`` ``2>`` ``2>>``, and
command lists joined by ``&&``, ``||`` and ``;``.

Parsing and expansion are separate steps: ``parse`` keeps words unexpanded and
the shell calls ``SimpleCommand.expand`` right before running each command,
so ``false; echo $?`` and ``cd dir && rm *.txt`` see up-to-date state.

Not supported (on purpose): subshells, functions, backgrounding, heredocs.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

OPERATORS = ("2>>", "&&", "||", ">>", "2>", "|", ";", ">", "<")
_VAR_RE = re.compile(r"\$(\?|[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})")
_GLOB_CHARS = set("*?[")

# Word part kinds
LITERAL = "literal"  # single quotes / backslash escapes: taken verbatim
QUOTED = "quoted"  # double quotes: variables expand, no globbing
BARE = "bare"  # unquoted: variables, ~ and globs expand


class ParseError(Exception):
    """Raised for unterminated quotes or dangling operators."""


def _expand_vars(text: str, env: Mapping[str, str]) -> str:
    return _VAR_RE.sub(lambda m: str(env.get(m.group(1).strip("{}"), "")), text)


@dataclass
class Word:
    parts: list[tuple[str, str]] = field(default_factory=list)  # (text, kind)

    @property
    def text(self) -> str:
        """The word as written (minus quotes), before expansion."""
        return "".join(t for t, _ in self.parts)

    @property
    def globbable(self) -> bool:
        return any(kind == BARE and _GLOB_CHARS & set(t) for t, kind in self.parts)

    def expand(self, env: Mapping[str, str], home: str,
               glob: Callable[[str], list[str]] | None = None) -> list[str]:
        out = []
        for i, (text, kind) in enumerate(self.parts):
            if kind == LITERAL:
                out.append(text)
                continue
            if kind == BARE and i == 0 and (text == "~" or text.startswith("~/")):
                text = home + text[1:]
            out.append(_expand_vars(text, env))
        result = "".join(out)
        if glob and self.globbable:
            return glob(result) or [result]
        return [result]


@dataclass
class Redirect:
    kind: str  # '>', '>>', '<', '2>', '2>>'
    word: Word

    def target(self, env: Mapping[str, str], home: str) -> str:
        return self.word.expand(env, home)[0]


@dataclass
class SimpleCommand:
    words: list[Word] = field(default_factory=list)
    redirects: list[Redirect] = field(default_factory=list)

    def expand(self, env: Mapping[str, str], home: str = "~",
               glob: Callable[[str], list[str]] | None = None) -> list[str]:
        argv: list[str] = []
        for word in self.words:
            argv.extend(word.expand(env, home, glob))
        return argv


@dataclass
class Pipeline:
    commands: list[SimpleCommand] = field(default_factory=list)


@dataclass
class CommandList:
    """A sequence of pipelines; ``ops[i]`` joins pipelines[i] to pipelines[i+1]."""

    pipelines: list[Pipeline] = field(default_factory=list)
    ops: list[str] = field(default_factory=list)

    def command_names(self) -> list[str]:
        """First word of every command, as written (used to spot `sudo` up front)."""
        return [c.words[0].text for p in self.pipelines for c in p.commands if c.words]

    def first_words(self) -> list[list[str]]:
        return [[w.text for w in c.words[:2]] for p in self.pipelines for c in p.commands if c.words]


def tokenize(line: str) -> list[object]:
    """Split ``line`` into Word and operator (str) tokens. Nothing is expanded."""
    tokens: list[object] = []
    word: Word | None = None
    i, n = 0, len(line)

    def add(text: str, kind: str) -> None:
        nonlocal word
        if word is None:
            word = Word()
        if word.parts and word.parts[-1][1] == kind:
            word.parts[-1] = (word.parts[-1][0] + text, kind)
        else:
            word.parts.append((text, kind))

    def flush() -> None:
        nonlocal word
        if word is not None:
            tokens.append(word)
        word = None

    while i < n:
        ch = line[i]
        if ch in " \t":
            flush()
            i += 1
            continue
        op = next((o for o in OPERATORS if line.startswith(o, i)), None)
        if op and op.startswith("2") and word is not None:
            op = None  # "file2>x" is a word followed by ">"
        if op:
            flush()
            tokens.append(op)
            i += len(op)
            continue
        if ch == "'":
            end = line.find("'", i + 1)
            if end == -1:
                raise ParseError("unterminated single quote")
            add(line[i + 1:end], LITERAL)
            i = end + 1
            continue
        if ch == '"':
            j = i + 1
            chunk: list[str] = []
            while j < n and line[j] != '"':
                if line[j] == "\\" and j + 1 < n and line[j + 1] in '"\\`':
                    chunk.append(line[j + 1])
                    j += 2
                    continue
                chunk.append(line[j])
                j += 1
            if j >= n:
                raise ParseError("unterminated double quote")
            add("".join(chunk), QUOTED)
            i = j + 1
            continue
        if ch == "\\" and i + 1 < n:
            add(line[i + 1], LITERAL)
            i += 2
            continue
        add(ch, BARE)
        i += 1
    flush()
    return tokens


def parse(line: str) -> CommandList:
    """Parse a full command line into a CommandList (unexpanded)."""
    tokens = tokenize(line)
    result = CommandList()
    pipeline = Pipeline()
    cmd = SimpleCommand()

    def end_command() -> None:
        nonlocal cmd
        if not cmd.words and not cmd.redirects:
            raise ParseError("syntax error near unexpected token")
        pipeline.commands.append(cmd)
        cmd = SimpleCommand()

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if isinstance(tok, Word):
            cmd.words.append(tok)
        elif tok in (">", ">>", "<", "2>", "2>>"):
            if i + 1 >= len(tokens) or not isinstance(tokens[i + 1], Word):
                raise ParseError(f"syntax error near unexpected token `{tok}'")
            cmd.redirects.append(Redirect(tok, tokens[i + 1]))
            i += 1
        elif tok == "|":
            end_command()
        elif tok in ("&&", "||", ";"):
            if cmd.words or cmd.redirects:
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

    if cmd.words or cmd.redirects:
        end_command()
    elif tokens and tokens[-1] == "|":
        raise ParseError("syntax error: unexpected end of input after `|'")
    if pipeline.commands:
        result.pipelines.append(pipeline)
    elif result.ops and result.ops[-1] == ";":
        result.ops.pop()
    elif result.ops:
        raise ParseError(f"syntax error: unexpected end of input after `{result.ops[-1]}'")
    return result
