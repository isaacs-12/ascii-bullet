import pytest

from src.shell.parser import ParseError, Word, parse, tokenize


def argvs(line, **kw):
    return [[c.argv for c in p.commands] for p in parse(line, **kw).pipelines]


def test_quotes_and_escapes():
    assert argvs("echo 'a b' \"c d\" e\\ f") == [[["echo", "a b", "c d", "e f"]]]


def test_variables_expand_outside_single_quotes():
    env = {"USER": "pilot", "?": "1"}
    assert argvs("echo $USER ${USER} '$USER' \"$USER\" $?", env=env) == [
        [["echo", "pilot", "pilot", "$USER", "pilot", "1"]]
    ]


def test_tilde_expands_only_at_word_start():
    assert argvs("cd ~/data a~b", home="/h") == [[["cd", "/h/data", "a~b"]]]


def test_pipes_lists_and_redirects():
    cl = parse("cat f | grep x > out.txt && echo ok || echo no; ls 2>/dev/null")
    assert cl.ops == ["&&", "||", ";"]
    first = cl.pipelines[0]
    assert [c.argv for c in first.commands] == [["cat", "f"], ["grep", "x"]]
    assert [(r.kind, r.target) for r in first.commands[1].redirects] == [(">", "out.txt")]
    assert [(r.kind, r.target) for r in cl.pipelines[3].commands[0].redirects] == [("2>", "/dev/null")]


def test_append_and_input_redirect():
    cmd = parse("sort < in.txt >> out.txt").pipelines[0].commands[0]
    assert [(r.kind, r.target) for r in cmd.redirects] == [("<", "in.txt"), (">>", "out.txt")]


def test_glob_callback_only_for_unquoted_words():
    seen = []

    def glob(p):
        seen.append(p)
        return ["a.txt", "b.txt"]

    assert argvs("cat *.txt '*.txt'", glob=glob) == [[["cat", "a.txt", "b.txt", "*.txt"]]]
    assert seen == ["*.txt"]


def test_glob_without_matches_keeps_literal():
    assert argvs("ls *.nope", glob=lambda p: []) == [[["ls", "*.nope"]]]


def test_trailing_semicolon_is_fine():
    assert argvs("echo hi;") == [[["echo", "hi"]]]


@pytest.mark.parametrize("line", ["echo 'unterminated", 'echo "x', "| grep", "ls |", "ls && ", "> "])
def test_syntax_errors(line):
    with pytest.raises(ParseError):
        parse(line)


def test_tokenize_marks_globbable_words():
    toks = tokenize("ls *.py 'x*'")
    assert toks[1] == Word("*.py", True)
    assert toks[2] == Word("x*", False)
