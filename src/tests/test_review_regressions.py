"""Regression tests for bugs found in review of the shell/VFS rewrite."""

import pytest

from src.shell.shell import SUDO_PASSWORD
from src.tests.helpers import make_shell
from src.unix.script_executor import ScriptExecutor


@pytest.fixture
def env():
    return make_shell()


def run(env, line):
    shell, ui = env
    ui.lines.clear()
    status = shell.run(line)
    return status, ui.text()


def sudo_auth(env):
    shell, _ = env
    shell.run("sudo -k")
    shell.run("sudo true")
    shell.submit(SUDO_PASSWORD)


# 1. sudo honours pipes, redirects and exit status
def test_sudo_output_can_be_redirected_and_piped(env):
    sudo_auth(env)
    run(env, "echo important > n.txt")
    run(env, "sudo echo new > n.txt")
    assert run(env, "cat n.txt")[1] == "new"
    assert run(env, "sudo whoami | grep root")[1] == "root"
    assert run(env, "sudo false && echo X")[1] == ""
    assert run(env, "sudo false || echo fallback")[1] == "fallback"


def test_sudo_prompts_before_running_the_whole_line(env):
    shell, ui = env
    run(env, "echo a > count.txt; sudo echo b >> count.txt")
    assert shell.session is not None  # nothing ran yet
    assert not shell.fs.file_exists("count.txt")
    shell.submit(SUDO_PASSWORD)
    shell.run("cat count.txt")
    assert ui.text().endswith("a\nb")


def test_sudo_override_conf_is_written(env):
    shell, _ = env
    sudo_auth(env)
    run(env, "sudo mkdir /etc/systemd/system/cooler.service.d")
    run(env, "sudo echo Conflicts=laser.service > /etc/systemd/system/cooler.service.d/override.conf")
    assert run(env, "cat /etc/systemd/system/cooler.service.d/override.conf")[1] == "Conflicts=laser.service"


# 2. the sandbox can't reach the filesystem object or outlive its deadline
@pytest.mark.parametrize("code", [
    "os.filesystem.set_user('root')",
    "f = open('x.txt', 'w')\nf.filesystem.set_user('root')",
    "os.path.filesystem.set_user('root')",
])
def test_sandbox_hides_internals(env, code):
    shell, _ = env
    ok, error = ScriptExecutor().execute(code, shell.fs, lambda line: None)
    assert not ok and "has no attribute" in error
    assert shell.fs.get_current_user() == "pilot"


@pytest.mark.parametrize("code", [
    "while True:\n    try:\n        while True:\n            pass\n    except Exception:\n        pass",
    "while True:\n    try:\n        while True:\n            pass\n    except:\n        pass",
    "def f():\n    try:\n        f()\n    except:\n        f()\nf()",
])
def test_sandbox_timeout_cannot_be_swallowed(env, code):
    shell, _ = env
    ex = ScriptExecutor()
    ex.MAX_EXECUTION_TIME = 0.3
    ok, error = ex.execute(code, shell.fs, lambda line: None)
    assert not ok and "timed out" in error


# 3. rm -r of several user directories
def test_rm_r_multiple_user_dirs(env):
    run(env, "mkdir foo bar")
    status, out = run(env, "rm -r foo bar")
    assert status == 0 and "internal error" not in out
    assert "foo" not in run(env, "ls")[1]


# 4. no ghost files named after directories
@pytest.mark.parametrize("line", ["touch data", "touch ~/", "touch data/", "echo hi > newf/"])
def test_no_ghost_files(env, line):
    run(env, line)
    listing = run(env, "ls -a")[1].split()
    assert listing.count("data") == 0 and "newf" not in listing
    assert "" not in run(env, "ls -1")[1].splitlines()


# 5. expansion happens per command
def test_status_and_pwd_expand_per_command(env):
    assert run(env, "false; echo $?")[1] == "1"
    assert run(env, "cd data; echo $PWD")[1] == "/home/pilot/blthll/data"
    run(env, "cd ~")


def test_globs_expand_after_cd(env):
    status, out = run(env, "cd games/minesweeper; ls .node_1*")
    assert ".node_1_2" in out
    run(env, "cd ~")


# 6. recreated / moved-back default files are readable
def test_move_default_file_away_and_back(env):
    run(env, "mv readme.txt r2")
    run(env, "mv r2 readme.txt")
    assert "Welcome to BLTHLL" in run(env, "cat readme.txt")[1]


def test_recreate_deleted_default_file(env):
    run(env, "rm manual.txt")
    run(env, "echo x > manual.txt")
    assert run(env, "cat manual.txt")[1] == "x"
    run(env, "rm manual.txt")
    assert run(env, "cat manual.txt")[0] != 0  # the default copy stays deleted


# 9. append only needs write permission
def test_append_to_write_only_file(env):
    run(env, "echo line1 > log")
    run(env, "chmod 200 log")
    run(env, "echo line2 >> log")
    run(env, "chmod 600 log")
    assert run(env, "cat log")[1] == "line1\nline2"


# 10. rmdir refuses non-empty dirs; mkdir won't shadow a file
def test_rmdir_with_subdirectory(env):
    run(env, "mkdir -p a/b")
    assert run(env, "rmdir a")[0] != 0
    assert run(env, "mkdir -p readme.txt/x")[0] != 0


# 11. small crashes
@pytest.mark.parametrize("line", ["echo -e 'a\\x'", "echo x | cut -c abc", "seq 100000000"])
def test_no_internal_errors(env, line):
    assert "internal error" not in run(env, line)[1]
