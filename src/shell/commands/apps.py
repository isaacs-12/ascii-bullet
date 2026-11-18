"""Commands that open full-screen apps: editors, viewers, python, animations."""

from __future__ import annotations

from src.shell.registry import command
from src.shell.text import Styled


def _open_editor(ctx, editor_name: str):
    if not ctx.args:
        ctx.err(f"Usage: {ctx.name} <file>")
        return 1
    target = ctx.args[0]
    if ctx.fs.is_directory_path(target):
        ctx.err(f"{ctx.name}: {target}: Is a directory")
        return 1
    from src.states.unix_utils.editor import EditorState

    fs = ctx.fs
    ctx.launch(lambda game, back: EditorState(game, fs, target, back, editor_name=editor_name))
    return 0


@command("vim")
def vim(ctx):
    return _open_editor(ctx, "vim")


@command("emacs", available=lambda shell: shell.game.save_system.is_package_installed("emacs"))
def emacs(ctx):
    return _open_editor(ctx, "emacs")


@command("nano")
def nano(ctx):
    ctx.out(Styled.plain("nano: Walnut Industries standardised on vim. Opening vim. Good luck.", "warn"))
    return _open_editor(ctx, "vim")


@command("code")
def code(ctx):
    from src.states.unix_utils.vscode_editor import VSCodeEditorState

    fs = ctx.fs
    ctx.launch(lambda game, back: VSCodeEditorState(game, fs, back))


@command("readme")
def readme(ctx):
    target = ctx.args[0] if ctx.args else None
    if target is None:
        for name in ("README.md", "README", "readme.md", "readme.txt", "readme"):
            if ctx.fs.file_exists(name):
                target = name
                break
    if target is None:
        ctx.err("readme: no README here. Try 'readme <file>'.")
        return 1
    ok, content = ctx.read(target)
    if not ok:
        ctx.err(f"readme: {content}")
        return 1
    if not ctx.interactive:
        ctx.out(*content)
        return 0
    from src.states.unix_utils.readme_viewer import ReadmeViewerState

    fs = ctx.fs
    ctx.launch(lambda game, back: ReadmeViewerState(game, fs, target, back))


@command("less")
def less(ctx):
    if not ctx.args and ctx.stdin is not None:
        ctx.out(*ctx.input_lines())
        return 0
    return readme(ctx)


@command("python")
def python(ctx):
    if not ctx.args:
        ctx.out(Styled.plain("Python 3.13.0 (walnut, sandboxed) on blthll", "accent"),
                "Interactive mode is not supported. Usage: python <script.py>",
                Styled.plain("tip: 'man python' lists what the sandbox allows", "dim"))
        return 0
    if ctx.args[0] in ("-c",) and len(ctx.args) > 1:
        code_lines = [" ".join(ctx.args[1:])]
        name = "<string>"
    else:
        name = ctx.args[0]
        if ctx.fs.is_directory_path(name) or not ctx.fs.file_exists(name):
            ctx.err(f"python: can't open file '{name}': [Errno 2] No such file or directory")
            return 2
        if not ctx.fs.check_permission(name, "x"):
            ctx.err(f"python: '{name}': Permission denied (hint: chmod +x {name})")
            return 126
        ok, code_lines = ctx.read(name)
        if not ok:
            ctx.err(f"python: {code_lines}")
            return 1
    from src.unix.script_executor import ScriptExecutor

    pm = ctx.shell.process_manager
    pid = pm.add_process(f"python {name}", cpu_usage=2.5, mem_usage=5.0)
    try:
        ok, error = ScriptExecutor().execute(code_lines, ctx.fs, ctx.out, ctx.shell.save_filesystem)
    finally:
        pm.remove_process(pid)
    if not ok:
        ctx.err(error)
        return 1
    return 0


@command("brew")
def brew(ctx):
    sub = ctx.args[0] if ctx.args else ""
    if sub == "update":
        ctx.typed([
            "==> Updating Homebrew...",
            "==> Downloading https://walnut.industries/taps/blthll/core.tar.gz",
            "######################################################################## 100.0%",
            "Updated 1 tap (blthll/core).",
            "==> New Formulae",
            "emacs        cowsay-pro (just cowsay)        bullet-time (coming soon)",
        ], delay=12)
        ctx.achieve("brew_update")
        return 0
    if sub == "install":
        pkg = ctx.args[1] if len(ctx.args) > 1 else ""
        if not pkg:
            ctx.err("Error: This command requires a formula argument")
            return 1
        if pkg != "emacs":
            ctx.err(f'Error: No available formula with the name "{pkg}". Try: brew update')
            return 1
        if ctx.save.is_package_installed("emacs"):
            ctx.out("Warning: emacs is already installed and up-to-date.")
            return 0
        ctx.typed([
            "==> Downloading emacs-29.blthll.bottle.tar.gz",
            "######################################################################## 100.0%",
            "==> Pouring emacs-29.blthll.bottle.tar.gz",
            "==> Installing a kitchen sink (emacs dependency)",
            "GNU Emacs installed. New command available: emacs <file>",
        ], delay=12)
        ctx.save.install_package("emacs")
        ctx.achieve("brew_emacs")
        return 0
    if sub == "list":
        ctx.out(*ctx.save.get_installed_packages())
        return 0
    if sub == "doctor":
        ctx.out("Your system is ready to brew.", "Warning: a process named something boring is using 30% CPU.")
        return 0
    ctx.out("Example usage:", "  brew update", "  brew install FORMULA", "  brew list", "  brew doctor")


@command("sl")
def sl(ctx):
    from src.states.unix_utils.fx_viewer import FxState

    ctx.launch(lambda game, back: FxState(game, back, "train"))


@command("cmatrix")
def cmatrix(ctx):
    from src.states.unix_utils.fx_viewer import FxState

    ctx.launch(lambda game, back: FxState(game, back, "rain"))
