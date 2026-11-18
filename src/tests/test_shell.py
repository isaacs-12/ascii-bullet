"""Behavioural tests for the BLTHLL shell (no window needed)."""

import pytest

from src.shell.shell import SUDO_PASSWORD
from src.tests.helpers import make_shell


@pytest.fixture
def env():
    shell, ui = make_shell()
    return shell, ui


def run(env, line):
    shell, ui = env
    ui.lines.clear()
    status = shell.run(line)
    return status, ui.text()


def test_pipeline_and_redirects(env):
    shell, _ = env
    run(env, "echo zebra > animals.txt")
    run(env, "echo aardvark >> animals.txt")
    status, out = run(env, "cat animals.txt | sort | head -n 1")
    assert status == 0 and out == "aardvark"
    assert run(env, "sort < animals.txt | tail -n 1")[1] == "zebra"
    assert run(env, "wc -l animals.txt")[1].split()[0] == "2"


def test_and_or_and_status(env):
    assert run(env, "false && echo nope || echo yes")[1] == "yes"
    run(env, "false")
    assert run(env, "echo $?")[1] == "1"


def test_unknown_command_suggests(env):
    status, out = run(env, "grpe foo")
    assert status == 127
    assert "command not found" in out and "grep" in out


def test_stderr_redirect_to_dev_null(env):
    status, out = run(env, "cat nope.txt 2>/dev/null")
    assert status == 1 and out == ""


def test_glob_expansion(env):
    out = run(env, "echo *.txt")[1]
    assert "manual.txt" in out and "readme.txt" in out
    hidden = run(env, "ls games/minesweeper/.node_*")[1]
    assert ".node_1_2" in hidden


def test_user_directories_are_listed(env):
    run(env, "mkdir -p stuff/inner")
    assert "stuff/" in run(env, "ls")[1]
    assert "inner/" in run(env, "ls stuff")[1]
    assert run(env, "cd stuff/inner && pwd")[1] == "/home/pilot/blthll/stuff/inner"
    run(env, "cd -")


def test_paths_everywhere(env):
    assert "SURVIVAL" in run(env, "cat ~/manual.txt")[1]
    assert run(env, "cd /tmp && touch note && ls")[1] == "note"
    run(env, "cd ~")
    assert "No such file" in run(env, "cat /nope/x")[1]


def test_chmod_symbolic_and_python(env):
    shell, _ = env
    run(env, "echo \"print('hi from script')\" > s.py")
    status, out = run(env, "chmod -x s.py; python s.py")
    assert "Permission denied" in out
    status, out = run(env, "chmod +x s.py && python s.py")
    assert status == 0 and "hi from script" in out


def test_history_bang_bang_and_alias(env):
    shell, _ = env
    run(env, "echo first")
    assert "first" in run(env, "!!")[1]
    run(env, "alias greet='echo hello'")
    assert run(env, "greet world")[1] == "hello world"


def test_export_and_env(env):
    run(env, "export WEAPON=bomb")
    assert run(env, "echo $WEAPON")[1] == "bomb"
    assert "API_KEY=(none needed" in run(env, "env")[1]


def test_sudo_requires_password_then_caches(env):
    shell, ui = env
    status, out = run(env, "cat /etc/shadow")
    assert "Permission denied" in out
    run(env, "sudo cat /etc/shadow")
    assert shell.session is not None and shell.session.secret
    shell.submit("wrong")
    assert "Sorry, try again." in ui.text()
    shell.submit(SUDO_PASSWORD)
    assert shell.session is None
    assert "wally:" in ui.text()
    assert shell.user == "pilot"  # privileges dropped afterwards
    ui.lines.clear()
    shell.run("sudo whoami")  # cached: no prompt
    assert ui.text().strip().endswith("root")


def test_sudo_three_strikes(env):
    shell, ui = env
    shell.run("sudo ls")
    for _ in range(3):
        shell.submit("nope")
    assert shell.session is None
    assert "3 incorrect password attempts" in ui.text()


def test_rm_guards_and_save_reset(env):
    shell, ui = env
    out = run(env, "rm -rf /")[1]
    assert "Cannot delete bullets" in out
    run(env, "touch keep.txt")
    run(env, "rm save --filesystem")
    assert "keep.txt" not in run(env, "ls")[1]


def test_systemctl_unlocks_after_install(env):
    assert run(env, "systemctl status laser")[0] == 127
    run(env, "mv /usr/local/deprecated/sys_control.py /bin/systemctl")
    run(env, "chmod +x /bin/systemctl")
    status, out = run(env, "systemctl status laser")
    assert "laser.service" in out


def test_dependency_puzzle_end_to_end(env):
    shell, ui = env
    for cmd in [
        "mv /usr/local/deprecated/sys_control.py /bin/systemctl",
        "chmod 755 /bin/systemctl",
        "mkdir /etc/systemd/system/cooler.service.d",
        "echo '[Unit]' > /etc/systemd/system/cooler.service.d/override.conf",
        "echo 'Conflicts=laser.service' >> /etc/systemd/system/cooler.service.d/override.conf",
    ]:
        shell.run(cmd)
    assert shell.game.save_system.is_game_unlocked("oregon_trail")
    assert "Oregon Trail unlocked" in ui.text()


def test_minesweeper_puzzle_via_shell(env):
    shell, ui = env
    shell.run("cd games/minesweeper && rm .node_1_2 .node_2_0")
    assert shell.game.save_system.is_game_unlocked("minesweeper")


def test_tab_completion(env):
    shell, _ = env
    assert shell.complete("cle") == ("clear ", [])
    assert shell.complete("cat man") == ("cat manual.txt ", [])
    assert shell.complete("cd da") == ("cd data/", [])
    new, options = shell.complete("cat games/minesweeper/.node_0")
    assert new.endswith(".node_0_") and len(options) == 3
    assert shell.complete("ls /us") == ("ls /usr/", [])


def test_launching_apps_is_deferred_to_ui(env):
    shell, ui = env
    shell.run("vim notes.txt")
    shell.run("start")
    assert len(ui.launched) == 2
    shell.run("vim notes.txt | cat")  # not interactive: no launch
    assert len(ui.launched) == 2


def test_hidden_files_and_secrets(env):
    shell, ui = env
    out = run(env, "cat data/secret/.transmission | base64 -d")[1]
    assert "godmode" in out
    assert shell.achievements.is_unlocked("codebreaker")
    out = run(env, "mail | grep Cvybg | rot13")[1]
    assert "sudo password" in out
    assert shell.achievements.is_unlocked("rot13")


def test_easter_phrases(env):
    shell, ui = env
    assert run(env, "sudo make me a sandwich")[1] == "Okay."
    assert shell.achievements.is_unlocked("sandwich")
    run(env, ":(){ :|:& };:")
    assert shell.achievements.is_unlocked("fork_bomb")
    assert "outside" in run(env, "touch grass")[1]
    assert "grass" not in run(env, "ls")[1]


def test_text_tools(env):
    assert run(env, "echo hello | rev")[1] == "olleh"
    assert run(env, "echo hello | tr a-z A-Z")[1] == "HELLO"
    assert run(env, "printf 2>/dev/null; seq 3 | nl | cut -f2")[1].split() == ["1", "2", "3"]
    assert run(env, "echo a b c | cut -d' ' -f2")[1] == "b"
    assert run(env, "echo aa; echo aa")[1].count("aa") == 2
    assert run(env, "seq 4 | sort -rn | uniq | head -n 1")[1] == "4"
    assert "#" in run(env, "figlet hi")[1]


def test_pipe_achievement_and_lolcat(env):
    shell, ui = env
    shell.run("fortune | cowsay | lolcat")
    for aid in ("pipe_dream", "moo", "fortune_teller", "rainbow"):
        assert shell.achievements.is_unlocked(aid), aid


def test_help_hides_hidden_commands(env):
    out = run(env, "help")[1]
    assert "claude" not in out and "godmode" not in out
    assert "start" in out and "grep" in out


def test_which_and_man(env):
    out = run(env, "which ls cd claude")[1]
    assert "/usr/bin/ls" in out and "built-in" in out and "/opt/walnut/ai/bin/claude" in out
    assert "pipes" in run(env, "man blsh")[1]
    assert run(env, "man definitely-not-a-thing")[0] != 0


def test_internal_errors_do_not_escape(env, monkeypatch):
    shell, ui = env
    spec = shell.registry["pwd"]

    def boom(ctx):
        raise RuntimeError("kaboom")

    monkeypatch.setitem(shell.registry, "pwd", spec.__class__(**{**spec.__dict__, "handler": boom}))
    status, out = run(env, "pwd")
    assert status == 1 and "internal error" in out
