"""Shell builtins and system commands."""

from __future__ import annotations

import time
from datetime import datetime

from src.shell.registry import command, load_json
from src.shell.shell import SUDO_PASSWORD, InputSession
from src.shell.text import Styled

# ----------------------------------------------------------------- builtins

@command("help")
def help_cmd(ctx):
    shell = ctx.shell
    if ctx.args:
        spec = shell.resolve(ctx.args[0])
        if not spec:
            ctx.err(f"help: no help topics match '{ctx.args[0]}'")
            return 1
        ctx.out(Styled.plain(spec.usage, "accent"), f"  {spec.summary}")
        if spec.aliases:
            ctx.out(Styled.plain(f"  aliases: {', '.join(spec.aliases)}", "dim"))
        ctx.out(Styled.plain(f"  more: man {spec.name}", "dim"))
        return 0
    categories = load_json("commands.json").get("_categories", {})
    seen: set[str] = set()
    by_cat: dict[str, list] = {}
    for spec in shell.registry.values():
        if spec.name in seen or spec.hidden or not spec.is_available(shell):
            continue
        seen.add(spec.name)
        by_cat.setdefault(spec.category, []).append(spec)
    for cat, title in categories.items():
        specs = sorted(by_cat.get(cat, []), key=lambda s: s.name)
        if not specs:
            continue
        ctx.out(Styled.plain(title, "title"))
        for spec in specs:
            ctx.out(Styled(("  " + spec.usage.ljust(26), "accent"), (spec.summary, None)))
        ctx.out("")
    for g in ("minesweeper", "set", "oregon_trail"):
        if ctx.save.is_game_unlocked(g):
            ctx.out(Styled(("  " + f"start {g}".ljust(26), "warn"), ("unlocked game", None)))
    ctx.out(Styled.plain("Pipes (|), redirects (> >> <), && || ; and globs (*) work. "
                         "TAB completes. 'man <cmd>' for details.", "dim"))
    ctx.out(Styled.plain("Some commands aren't listed. Explore.", "dim"))


@command("man")
def man(ctx):
    if not ctx.args:
        ctx.err("What manual page do you want?", "For example, try 'man man'.")
        return 1
    topic = ctx.args[-1].lower()
    pages = load_json("man_pages.json")
    page = pages.get(topic)
    spec = ctx.shell.resolve(topic)
    if page is None and spec is not None and not spec.hidden:
        page = [
            f"{spec.name.upper()}(1)", "", "NAME", f"       {spec.name} - {spec.summary}", "",
            "SYNOPSIS", f"       {spec.usage}",
        ]
        if spec.aliases:
            page += ["", "ALIASES", "       " + ", ".join(spec.aliases)]
    if page is None:
        ctx.err(f"No manual entry for {topic}")
        return 16
    header = page[0]
    ctx.out(Styled.plain(f"{header}{'BLTHLL Manual'.center(max(0, 60 - 2 * len(header)))}{header}", "title"))
    for line in page[1:]:
        if line and line == line.upper() and not line.startswith(" "):
            ctx.out(Styled.plain(line, "accent"))
        else:
            ctx.out(line)


@command("clear")
def clear(ctx):
    ctx.shell.ui.clear()


@command("history")
def history(ctx):
    if ctx.args and ctx.args[0] == "-c":
        ctx.shell.history.clear()
        ctx.save.save_command_history([])
        return 0
    entries = ctx.shell.history
    if ctx.args and ctx.args[0].isdigit():
        entries = entries[-int(ctx.args[0]):]
    offset = len(ctx.shell.history) - len(entries)
    for i, cmd in enumerate(entries, offset + 1):
        ctx.out(f"{i:5}  {cmd}")


@command("which")
def which(ctx):
    if not ctx.args:
        ctx.err("Usage: which <command>")
        return 1
    status = 0
    for name in ctx.args:
        if name in ctx.shell.aliases:
            ctx.out(f"{name}: aliased to '{ctx.shell.aliases[name]}'")
            continue
        spec = ctx.shell.resolve(name)
        if spec:
            ctx.out(spec.path or f"{name}: shell built-in command")
        else:
            ctx.err(f"{name} not found")
            status = 1
    return status


@command("alias")
def alias(ctx):
    if not ctx.args:
        for k, v in sorted(ctx.shell.aliases.items()):
            ctx.out(f"alias {k}='{v}'")
        return 0
    for arg in ctx.args:
        name, eq, value = arg.partition("=")
        if not eq:
            if name in ctx.shell.aliases:
                ctx.out(f"alias {name}='{ctx.shell.aliases[name]}'")
            else:
                ctx.err(f"alias: {name}: not found")
                return 1
        else:
            ctx.shell.aliases[name] = value
    return 0


@command("unalias")
def unalias(ctx):
    for name in ctx.args:
        ctx.shell.aliases.pop(name, None)


@command("export")
def export(ctx):
    if not ctx.args:
        return env(ctx)
    for arg in ctx.args:
        name, eq, value = arg.partition("=")
        if eq and name.replace("_", "").isalnum():
            ctx.shell.env[name] = value
        else:
            ctx.err(f"export: '{arg}': not a valid identifier")
            return 1
    return 0


@command("env")
def env(ctx):
    view = ctx.shell._env_view()
    view.pop("?", None)
    for k in sorted(view):
        ctx.out(f"{k}={view[k]}")


@command("true")
def true_cmd(ctx):
    return 0


@command("false")
def false_cmd(ctx):
    return 1


@command("exit")
def exit_cmd(ctx):
    if ctx.fs.get_current_user() == "root" and ctx.shell._root_depth == 0:
        ctx.fs.set_user("pilot")
        ctx.out("logout")
        return 0
    ctx.save.save_command_history(ctx.shell.history)
    ctx.out("Shutting down... (your progress is saved)")
    ctx.shell.ui.quit()


# ---------------------------------------------------------------- identity

@command("whoami")
def whoami(ctx):
    ctx.out(ctx.fs.get_current_user())


@command("id")
def id_cmd(ctx):
    if ctx.fs.get_current_user() == "root":
        ctx.out("uid=0(root) gid=0(root) groups=0(root)")
    else:
        ctx.out("uid=1000(pilot) gid=1000(pilot) groups=1000(pilot),27(sudo-ish),1337(bullets)")


@command("hostname")
def hostname(ctx):
    ctx.out("blthll")


@command("uname")
def uname(ctx):
    if any(a in ("-a", "--all") for a in ctx.args):
        ctx.out("BLTHLL blthll 0.2.0-graze #1 SMP PREEMPT_BULLET walnut64 GNU/Linux")
    elif "-r" in ctx.args:
        ctx.out("0.2.0-graze")
    elif "-m" in ctx.args:
        ctx.out("walnut64")
    else:
        ctx.out("BLTHLL")


@command("date")
def date(ctx):
    ctx.out(datetime.now().strftime("%a %b %d %H:%M:%S %Y"))


def _uptime_str() -> str:
    import pygame

    secs = pygame.time.get_ticks() // 1000 if pygame.get_init() else int(time.monotonic())
    return f"{secs // 3600}:{(secs % 3600) // 60:02d}"


@command("uptime")
def uptime(ctx):
    load = ctx.shell.process_manager.virus_active
    avg = "13.37, 12.00, 11.11" if load else "0.42, 0.38, 0.35"
    ctx.out(f" {datetime.now():%H:%M:%S} up {_uptime_str()}, 1 user, load average: {avg}")


@command("neofetch")
def neofetch(ctx):
    art = load_json("art.json")["logo"]
    save = ctx.save
    found, total = ctx.shell.achievements.summary()
    info = [
        (f"{ctx.fs.get_current_user()}@blthll", "accent"),
        ("-" * 18, "dim"),
        ("OS: BLTHLL OS 0.2.0 (Graze Edition)", None),
        ("Kernel: 0.2.0-graze", None),
        (f"Uptime: {_uptime_str()}", None),
        (f"Shell: blsh (theme: {ctx.game.renderer.theme_name})", None),
        ("CPU: Walnut W-1 @ 3.14GHz" + (" (98% used?!)" if ctx.shell.process_manager.virus_active else ""), None),
        ("GPU: 1x character grid", None),
        (f"Best score: {save.get_best_score():,}", None),
        (f"Achievements: {found}/{total}", None),
        ("AI: 5 assistants, 0 API keys", None),
    ]
    width = max(len(x) for x in art) + 3
    for i in range(max(len(art), len(info))):
        left = art[i] if i < len(art) else ""
        text, color = info[i] if i < len(info) else ("", None)
        ctx.out(Styled((left.ljust(width), "accent"), (text, color)))
    palette = Styled(*[("███", c) for c in ("error", "warn", "fg", "accent", "title", "menu_normal", "dim")])
    ctx.out("", Styled((" " * width, None), *palette.segments))


@command("theme")
def theme(ctx):
    renderer = ctx.game.renderer
    if not ctx.args:
        ctx.out(f"current theme: {renderer.theme_name}")
        ctx.out("available: " + ", ".join(sorted(renderer.themes)))
        return 0
    name = ctx.args[0].lower()
    if not renderer.set_theme(name):
        ctx.err(f"theme: unknown theme '{name}' (try: {', '.join(sorted(renderer.themes))})")
        return 1
    ctx.save.update_setting("theme", name)
    ctx.out(f"theme set to {name}")


@command("crt")
def crt(ctx):
    renderer = ctx.game.renderer
    if ctx.args and ctx.args[0] in ("on", "off"):
        renderer.crt_enabled = ctx.args[0] == "on"
    else:
        renderer.crt_enabled = not renderer.crt_enabled
    ctx.save.update_setting("crt", renderer.crt_enabled)
    ctx.out(f"CRT scanlines {'on' if renderer.crt_enabled else 'off'}")


@command("shake")
def shake(ctx):
    renderer = ctx.game.renderer
    if ctx.args and ctx.args[0] in ("on", "off"):
        renderer.shake_enabled = ctx.args[0] == "on"
    else:
        renderer.shake_enabled = not renderer.shake_enabled
    ctx.save.update_setting("screen_shake", renderer.shake_enabled)
    ctx.out(f"screen shake {'on' if renderer.shake_enabled else 'off'}")
    if renderer.shake_enabled:
        renderer.shake(6, 0.3)


@command("sound")
def sound(ctx):
    sfx = getattr(ctx.game, "sfx", None)
    if sfx is None:
        ctx.err("sound: no audio device")
        return 1
    if ctx.args and ctx.args[0] in ("on", "off"):
        sfx.enabled = ctx.args[0] == "on"
    else:
        sfx.enabled = not sfx.enabled
    ctx.save.update_setting("sound", sfx.enabled)
    ctx.out(f"sound {'on' if sfx.enabled else 'off'}")
    sfx.play("achievement")


@command("df")
def df(ctx):
    used = ctx.fs._get_user_files_size()
    cap = ctx.fs.MAX_USER_FILES_SIZE
    ctx.out("Filesystem      Size  Used Avail Use% Mounted on")
    ctx.out(f"/dev/walnut0    {cap // 1024}K  {used // 1024 or 1}K  {(cap - used) // 1024}K  "
            f"{used * 100 // cap:>3}% /")
    ctx.out("bullets         inf   inf     0 100% /dev/hell")


@command("free")
def free(ctx):
    hog = 600 if ctx.shell.process_manager.virus_active else 120
    ctx.out("               total        used        free", f"Mem:             640         {hog}         {640 - hog}")


@command("mail")
def mail(ctx):
    ok, lines = ctx.read("/var/mail/pilot")
    if not ok:
        ctx.err(f"mail: {lines}")
        return 1
    ctx.out(*lines)


# ---------------------------------------------------------------- processes

@command("ps")
def ps(ctx):
    pm = ctx.shell.process_manager
    pm.update_cpu_usage()
    ctx.out(Styled.plain(f"{'PID':>6} {'USER':<8} {'%CPU':>5} {'MEM':>7}  {'TIME':>9}  COMMAND", "title"))
    for p in pm.get_processes():
        ctx.out(f"{p.pid:>6} {p.user:<8} {p.cpu:5.1f} {p.mem:6.1f}M  {p.time_str:>9}  {p.command}")


@command("top")
def top(ctx):
    from src.states.unix_utils.top_viewer import TopViewerState

    shell = ctx.shell
    pm = shell.process_manager
    ctx.launch(lambda game, back: TopViewerState(game, pm, back,
                                                 on_kill=lambda pid: shell.run(f"kill {pid}", record=False)))


@command("kill")
def kill(ctx):
    pids = [a for a in ctx.args if not a.startswith("-")]
    if not pids:
        ctx.err("kill: usage: kill [-signal] <pid>")
        return 1
    status = 0
    for pid_str in pids:
        try:
            pid = int(pid_str)
        except ValueError:
            ctx.err(f"kill: {pid_str}: arguments must be process IDs")
            status = 1
            continue
        status |= kill_process(ctx, pid)
    return status


def kill_process(ctx, pid: int) -> int:
    pm = ctx.shell.process_manager
    proc = pm.get_process(pid)
    if proc and proc.user == "root" and ctx.fs.get_current_user() != "root" and not getattr(proc, "is_virus", False):
        ctx.err(f"kill: ({pid}) - Operation not permitted")
        return 1
    ok, message, was_virus = pm.remove_process(pid)
    if not ok:
        ctx.err(message)
        return 1
    ctx.out(message)
    if was_virus:
        ctx.save.mark_virus_killed()
        pm.mark_virus_discovered()
        ctx.achieve("virus_hunter")
        ctx.game.renderer.flash((255, 60, 60), 0.3)
        ctx.game.renderer.shake(8, 0.4)
        bar = "=" * 50
        ctx.typed([bar, "ALERT: Malicious process terminated!", bar, "",
                   "Threat neutralized. CPU usage back to normal.",
                   "The spacebullets cabinet whirs to life...", "",
                   "New command unlocked: 'start spacebullets'", ""], delay=12)
    return 0


# ------------------------------------------------------------------ sudo

def _run_as_root(ctx, line: str) -> None:
    shell = ctx.shell
    with shell.as_root():
        shell.run(line, record=False)
    ctx.achieve("sudo_user")


@command("sudo")
def sudo(ctx):
    shell = ctx.shell
    if not ctx.args:
        ctx.err("usage: sudo <command>")
        return 1
    if ctx.args[0] in ("-k", "-K"):
        shell.sudo_until = 0
        return 0
    if ctx.args[0] == "-i" or ctx.args[0] == "su":
        line = None
    else:
        line = " ".join(_quote(a) for a in ctx.args)

    def proceed() -> None:
        if line is None:
            ctx.fs.set_user("root")
            shell.ui.write(Styled.plain("root shell. type 'exit' to drop privileges. be careful.", "error"))
            ctx.achieve("sudo_user")
        else:
            _run_as_root(ctx, line)

    if shell.sudo_valid() or ctx.fs.get_current_user() == "root":
        shell.flush_pending(ctx)
        proceed()
        return 0

    attempts = {"n": 0}

    def on_line(password: str) -> bool:
        if password == SUDO_PASSWORD:
            shell.grant_sudo()
            proceed()
            return False
        attempts["n"] += 1
        if attempts["n"] >= 3:
            shell.ui.write(Styled.plain("sudo: 3 incorrect password attempts", "error"))
            shell.ui.write(Styled.plain("hint: people leave passwords in the strangest places. "
                                        "like their shell history.", "dim"))
            return False
        shell.ui.write(Styled.plain("Sorry, try again.", "error"))
        return True

    ctx.start_session(InputSession(prompt=f"[sudo] password for {ctx.fs.get_current_user()}: ",
                                   on_line=on_line, secret=True))
    return 0


def _quote(arg: str) -> str:
    if not arg or any(c in arg for c in " \t'\"|&;<>*?$"):
        return "'" + arg.replace("'", "'\\''") + "'"
    return arg


@command("su")
def su(ctx):
    target = ctx.args[0] if ctx.args else "root"
    if target == "pilot":
        ctx.fs.set_user("pilot")
        return 0
    if target == "wally":
        ctx.err("su: Authentication failure (account disabled by HR)")
        return 1
    if target != "root":
        ctx.err(f"su: user {target} does not exist")
        return 1
    ctx.err("su: root has no password here. try 'sudo -i'.")
    return 1


# --------------------------------------------------------------- systemctl

def _systemctl_available(shell) -> bool:
    fs = shell.fs
    if not fs.file_exists("/bin/systemctl"):
        return False
    perms = fs.get_permissions("/bin/systemctl") or ""
    return "x" in perms[:3]


@command("systemctl", available=_systemctl_available)
def systemctl(ctx):
    sd = ctx.shell.systemd
    usage = "Usage: systemctl {status|start|stop|restart|enable|disable|list-units|list-unit-files} [unit]"
    if not ctx.args:
        return _list_units(ctx)
    sub, rest = ctx.args[0].lower(), ctx.args[1:]
    if sub in ("list-units", "--all"):
        return _list_units(ctx)
    if sub == "list-unit-files":
        files = sd.list_unit_files()
        ctx.out(Styled.plain(f"{'UNIT FILE':<32} {'STATE':<10} LOCATION", "title"))
        for name, location, enabled in files:
            ctx.out(f"{name:<32} {'enabled' if enabled else 'disabled':<10} {location}")
        ctx.out("", f"{len(files)} unit files listed.")
        return 0
    if sub not in ("status", "start", "stop", "restart", "enable", "disable", "cat"):
        ctx.err(f"systemctl: unknown command '{sub}'", usage)
        return 1
    if not rest:
        ctx.err(f"systemctl {sub}: missing unit name", usage)
        return 1
    status = 0
    for unit in rest:
        status |= _systemctl_one(ctx, sub, unit)
    ctx.shell.save_filesystem()
    return status


def _list_units(ctx):
    units = ctx.shell.systemd.list_units()
    ctx.out(Styled.plain(f"{'UNIT':<28} {'LOAD':<7} {'ACTIVE':<10} {'SUB':<8} ENABLED", "title"))
    for name, state, enabled in units:
        color = "fg" if state == "active" else ("error" if state == "failed" else "dim")
        ctx.out(Styled.plain(f"{name:<28} {'loaded':<7} {state:<10} "
                             f"{'running' if state == 'active' else 'dead':<8} "
                             f"{'enabled' if enabled else 'disabled'}", color))
    ctx.out("", f"{len(units)} loaded units listed.")
    return 0


def _systemctl_one(ctx, sub: str, unit: str) -> int:
    sd = ctx.shell.systemd
    name = unit if unit.endswith(".service") else unit + ".service"
    if sub in ("enable", "disable") and ctx.fs.get_current_user() != "root":
        ctx.err("Failed to " + sub + " unit: Access denied", "(try: sudo systemctl " + sub + " " + unit + ")")
        return 1
    if not sd._unit_file_exists(name):
        ctx.err(f"Unit {name} could not be found.")
        return 4
    if sub == "status":
        state = sd.get_service_state(name)
        enabled = sd.is_enabled(name)
        dot_color = "fg" if state == "active" else ("error" if state == "failed" else "dim")
        content = (sd._get_unit_file_content(name) or "").split("\n")
        desc = next((x.split("=", 1)[1] for x in content if x.startswith("Description=")), name)
        ctx.out(Styled(("● " if state != "inactive" else "○ ", dot_color), (f"{name} - {desc}", None)))
        ctx.out(f"     Loaded: loaded ({sd._resolve_unit_path(name)}; {'enabled' if enabled else 'disabled'})")
        ctx.out(Styled(("     Active: ", None), (state, dot_color)))
        return 0 if state == "active" else 3
    if sub == "cat":
        ctx.out(Styled.plain(f"# {sd._resolve_unit_path(name)}", "dim"),
                *(sd._get_unit_file_content(name) or "").split("\n"))
        return 0
    sd.clear_reset_flag()
    if sub == "restart":
        sd.stop_service(name)
        ok, message = sd.start_service(name)
    elif sub == "start":
        ok, message = sd.start_service(name)
    elif sub == "stop":
        ok, message = sd.stop_service(name)
    elif sub == "enable":
        ok, message = sd.enable_service(name)
    else:
        ok, message = sd.disable_service(name)
    for line in str(message).split("\n"):
        if ok:
            ctx.out(line)
        else:
            ctx.err(line)
    if sd.was_system_reset_triggered():
        ctx.out(Styled.plain("=" * 50, "error"), Styled.plain("SYSTEM RESET DETECTED", "error"),
                Styled.plain("=" * 50, "error"))
        ctx.game.renderer.shake(10, 0.5)
        sd.clear_reset_flag()
    return 0 if ok else 1
