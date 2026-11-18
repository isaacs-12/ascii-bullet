"""Filesystem commands: ls, cd, cat, grep, find, cp, mv, rm, chmod, ..."""

from __future__ import annotations

import fnmatch
import re
from datetime import datetime

from src.shell.registry import command
from src.shell.text import Styled, columns


def _split_flags(args: list[str], allowed: str = "") -> tuple[set[str], list[str], str | None]:
    """Split ``-abc`` style flags from operands. Returns (flags, operands, bad_flag)."""
    flags: set[str] = set()
    operands: list[str] = []
    end_of_flags = False
    for a in args:
        if not end_of_flags and a == "--":
            end_of_flags = True
        elif not end_of_flags and a.startswith("-") and len(a) > 1 and not a[1:].isdigit():
            for ch in a[1:]:
                if allowed and ch not in allowed:
                    return flags, operands, ch
                flags.add(ch)
        else:
            operands.append(a)
    return flags, operands, None


def file_size(fs, path: str) -> int:
    ok, content = fs.read_file(path)
    if not ok:
        return 0
    lines = [str(x) for x in content]
    return sum(len(x) for x in lines) + max(0, len(lines) - 1)


def _perm_string(perms: str | None) -> str:
    perms = perms or "rwxrwxrwx"
    if len(perms) == 3:
        perms *= 3
    return perms.ljust(9, "-")[:9]


def _long_entry(ctx, base: str, item: str) -> Styled:
    fs = ctx.fs
    is_dir = item.endswith("/")
    name = item.rstrip("/")
    path = f"{base.rstrip('/')}/{name}" if base else name
    if is_dir:
        saved = fs.current_path[:]
        fs.current_path = fs.normalize(path)[:-1]
        perms = fs.get_permissions(name) or "rwxr-xr-x"
        owner = fs.get_file_owner(name) or "root"
        fs.current_path = saved
        size = 4096
    else:
        perms = fs.get_permissions(path)
        owner = fs.get_file_owner(path) or fs.get_current_user()
        size = file_size(fs, path)
    ts = fs._get_timestamp(fs.abspath(path), "modify")
    try:
        when = datetime.fromisoformat(ts).strftime("%b %d %H:%M")
    except (TypeError, ValueError):
        when = "Jan 01 00:00"
    kind = "d" if is_dir else "-"
    color = "accent" if is_dir else ("warn" if "x" in _perm_string(perms)[:3] and not is_dir else "fg")
    return Styled(
        (f"{kind}{_perm_string(perms)}  {owner:<9} {size:>6} {when}  ", "dim"),
        (item if is_dir else name, color),
    )


@command("ls")
def ls(ctx):
    flags, operands, bad = _split_flags(ctx.args, "laA1hRF")
    if bad:
        ctx.err(f"ls: invalid option -- '{bad}'", "Try 'man ls' for more information.")
        return 2
    show_hidden = "a" in flags or "A" in flags
    targets = operands or ["."]
    status = 0
    for idx, target in enumerate(targets):
        fs = ctx.fs
        if not fs.is_directory_path(target):
            if fs.file_exists(target):
                ctx.out(_long_entry(ctx, "", target) if "l" in flags else target)
                continue
            ctx.err(f"ls: cannot access '{target}': No such file or directory")
            status = 2
            continue
        ok, items = fs.list_directory_at_path(target, show_hidden=show_hidden)
        if not ok:
            ctx.err(items)
            status = 2
            continue
        if len(targets) > 1:
            if idx:
                ctx.out("")
            ctx.out(f"{target}:")
        if "l" in flags:
            ctx.out(Styled.plain(f"total {len(items)}", "dim"))
            if "a" in flags:
                ctx.out(Styled(("drwxr-xr-x  " + f"{fs.get_current_user():<9} {4096:>6} ", "dim"), (".", "accent")))
                ctx.out(Styled(("drwxr-xr-x  " + f"{'root':<9} {4096:>6} ", "dim"), ("..", "accent")))
            for item in items:
                ctx.out(_long_entry(ctx, target, item))
        elif not ctx.interactive or "1" in flags:
            ctx.out(*[i.rstrip("/") if not ctx.interactive else i for i in items])
        else:
            for row in columns(items, max(20, ctx.width - 2)):
                ctx.out(_colorize_row(row, items))
    ctx.fs and ctx.save.mark_directory_visited(ctx.fs.get_pwd())
    return status


def _colorize_row(row: str, items: list[str]) -> Styled:
    dirs = {i for i in items if i.endswith("/")}
    segments = []
    for token in re.split(r"(\s+)", row):
        if not token:
            continue
        if token.isspace():
            segments.append((token, None))
        else:
            segments.append((token, "accent" if token in dirs else ("dim" if token.startswith(".") else "fg")))
    return Styled(*segments)


@command("cd")
def cd(ctx):
    target = ctx.args[0] if ctx.args else "~"
    if target == "-":
        target = ctx.shell.env.get("OLDPWD", "~")
    previous = ctx.fs.get_pwd()
    ok, error = ctx.fs.change_directory(target)
    if not ok:
        ctx.err(error)
        return 1
    ctx.shell.env["OLDPWD"] = previous
    visited = ctx.fs.get_pwd()
    ctx.save.mark_directory_visited(visited)
    if ctx.save.get_exploration_stats()["dirs_visited"] >= 15:
        ctx.achieve("explorer")
    return 0


@command("pwd")
def pwd(ctx):
    ctx.out(ctx.fs.get_pwd())


@command("cat")
def cat(ctx):
    flags, paths, bad = _split_flags(ctx.args, "n")
    if bad:
        ctx.err(f"cat: invalid option -- '{bad}'")
        return 1
    if not paths and ctx.stdin is None:
        ctx.err("cat: missing file operand", "Usage: cat <file>...")
        return 1
    lines, status = ctx.read_inputs(paths)
    if "n" in flags:
        lines = [f"{i:6}  {line}" for i, line in enumerate(lines, 1)]
    ctx.out(*lines)
    return status


def _parse_count(args: list[str], default: int = 10) -> tuple[int, list[str]]:
    count = default
    rest: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-n" and i + 1 < len(args):
            try:
                count = int(args[i + 1])
            except ValueError:
                pass
            i += 2
            continue
        if a.startswith("-") and a[1:].isdigit():
            count = int(a[1:])
        else:
            rest.append(a)
        i += 1
    return count, rest


@command("head")
def head(ctx):
    count, paths = _parse_count(ctx.args)
    if not paths and ctx.stdin is None:
        ctx.err("head: missing file operand", "Usage: head [-n N] <file>")
        return 1
    lines, status = ctx.read_inputs(paths)
    ctx.out(*lines[:count])
    return status


@command("tail")
def tail(ctx):
    count, paths = _parse_count(ctx.args)
    if not paths and ctx.stdin is None:
        ctx.err("tail: missing file operand", "Usage: tail [-n N] <file>")
        return 1
    lines, status = ctx.read_inputs(paths)
    ctx.out(*(lines[-count:] if count else []))
    return status


@command("grep")
def grep(ctx):
    flags, operands, bad = _split_flags(ctx.args, "invcrlE")
    if bad:
        ctx.err(f"grep: invalid option -- '{bad}'")
        return 2
    if not operands:
        ctx.err("grep: missing pattern", "Usage: grep [-invc] <pattern> [file...]")
        return 2
    pattern, paths = operands[0], operands[1:]
    try:
        regex = re.compile(pattern, re.IGNORECASE if "i" in flags else 0)
    except re.error:
        regex = re.compile(re.escape(pattern), re.IGNORECASE if "i" in flags else 0)

    sources: list[tuple[str, list[str]]] = []
    status = 0
    if "r" in flags:
        for root in paths or ["."]:
            for dirpath, _dirs, files in ctx.fs.walk_directory(root):
                for f in files:
                    path = f"{dirpath.rstrip('/')}/{f}"
                    ok, content = ctx.fs.read_file(path)
                    if ok:
                        sources.append((path, [str(x) for x in content]))
    elif paths:
        for p in paths:
            ok, content = ctx.read(p)
            if ok:
                sources.append((p, content))
            else:
                ctx.err(f"grep: {content}")
                status = 2
    else:
        sources.append(("(standard input)", ctx.input_lines()))

    show_names = len(sources) > 1 or "r" in flags
    matched_any = False
    for name, lines in sources:
        count = 0
        for i, line in enumerate(lines, 1):
            hit = bool(regex.search(line)) != ("v" in flags)
            if not hit:
                continue
            matched_any = True
            count += 1
            if "c" in flags or "l" in flags:
                continue
            prefix = (f"{name}:" if show_names else "") + (f"{i}:" if "n" in flags else "")
            if ctx.interactive and "v" not in flags:
                ctx.out(_highlight(prefix, line, regex))
            else:
                ctx.out(prefix + line)
        if "c" in flags:
            ctx.out((f"{name}:" if show_names else "") + str(count))
        elif "l" in flags and count:
            ctx.out(name)
    if status:
        return status
    return 0 if matched_any else 1


def _highlight(prefix: str, line: str, regex: re.Pattern) -> Styled:
    segments: list[tuple[str, object]] = [(prefix, "accent")] if prefix else []
    pos = 0
    for m in regex.finditer(line):
        if m.start() == m.end():
            continue
        segments.append((line[pos:m.start()], None))
        segments.append((m.group(0), "error"))
        pos = m.end()
    segments.append((line[pos:], None))
    return Styled(*segments)


@command("wc")
def wc(ctx):
    flags, paths, bad = _split_flags(ctx.args, "lwc")
    if bad:
        ctx.err(f"wc: invalid option -- '{bad}'")
        return 1
    if not paths and ctx.stdin is None:
        ctx.err("wc: missing file operand", "Usage: wc [-lwc] <file>")
        return 1
    show = flags or {"l", "w", "c"}
    sources = [(p, None) for p in paths] or [("", ctx.input_lines())]
    status = 0
    for name, lines in sources:
        if lines is None:
            ok, lines = ctx.read(name)
            if not ok:
                ctx.err(f"wc: {lines}")
                status = 1
                continue
        counts = {
            "l": len(lines),
            "w": sum(len(x.split()) for x in lines),
            "c": sum(len(x) + 1 for x in lines),
        }
        parts = [f"{counts[k]:>7}" for k in "lwc" if k in show]
        ctx.out("".join(parts) + (f" {name}" if name else ""))
    return status


@command("find")
def find(ctx):
    root = "."
    name_pattern = None
    kind = None
    args = ctx.args
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-name", "-iname") and i + 1 < len(args):
            name_pattern = (args[i + 1], a == "-iname")
            i += 2
        elif a == "-type" and i + 1 < len(args):
            kind = args[i + 1]
            i += 2
        elif not a.startswith("-"):
            root = a
            i += 1
        else:
            ctx.err(f"find: unknown predicate '{a}'")
            return 1
    if not ctx.fs.is_directory_path(root):
        ctx.err(f"find: '{root}': No such file or directory")
        return 1

    def matches(name: str) -> bool:
        if not name_pattern:
            return True
        pat, ci = name_pattern
        return fnmatch.fnmatchcase(name.lower(), pat.lower()) if ci else fnmatch.fnmatchcase(name, pat)

    root_abs = ctx.fs.abspath(root)
    if kind in (None, "d") and matches(root_abs.rsplit("/", 1)[-1] or "/"):
        ctx.out(root)
    for dirpath, dirnames, filenames in ctx.fs.walk_directory(root):
        rel = dirpath[len(root_abs):] if dirpath.startswith(root_abs) else dirpath
        display = (root.rstrip("/") + rel) if root not in ("/",) else dirpath
        for d in dirnames:
            if kind in (None, "d") and matches(d):
                ctx.out(f"{display.rstrip('/')}/{d}")
        for f in filenames:
            if kind in (None, "f") and matches(f):
                ctx.out(f"{display.rstrip('/')}/{f}")
    return 0


@command("tree")
def tree(ctx):
    flags, operands, _ = _split_flags(ctx.args, "a")
    root = operands[0] if operands else "."
    if not ctx.fs.is_directory_path(root):
        ctx.err(f"tree: '{root}': No such directory")
        return 1
    counts = {"d": 0, "f": 0}
    ctx.out(Styled.plain(root, "accent"))

    def walk(path: str, prefix: str, depth: int) -> None:
        if depth > 8:
            return
        ok, items = ctx.fs.list_directory_at_path(path, show_hidden="a" in flags)
        if not ok:
            return
        for idx, item in enumerate(items):
            last = idx == len(items) - 1
            branch = "└── " if last else "├── "
            is_dir = item.endswith("/")
            counts["d" if is_dir else "f"] += 1
            ctx.out(Styled((prefix + branch, "dim"), (item.rstrip("/"), "accent" if is_dir else None)))
            if is_dir:
                walk(f"{path.rstrip('/')}/{item.rstrip('/')}", prefix + ("    " if last else "│   "), depth + 1)

    walk(root, "", 0)
    ctx.out("", f"{counts['d']} directories, {counts['f']} files")


@command("cp")
def cp(ctx):
    _flags, operands, _ = _split_flags(ctx.args, "rfi")
    if len(operands) != 2:
        ctx.err("cp: missing file operand", "Usage: cp <source> <destination>")
        return 1
    ok, error = ctx.fs.copy_file(*operands)
    if not ok:
        ctx.err(error)
        return 1
    ctx.shell.save_filesystem()


@command("mv")
def mv(ctx):
    _flags, operands, _ = _split_flags(ctx.args, "fi")
    if len(operands) != 2:
        ctx.err("mv: missing file operand", "Usage: mv <source> <destination>")
        return 1
    ok, error = ctx.fs.move_file(*operands)
    if not ok:
        ctx.err(f"mv: {error}")
        return 1
    ctx.shell.save_filesystem()


_PROTECTED = {"/", "/home", "/usr", "/etc", "/var", "/bin", "/system", "/opt", "/proc", "/home/pilot"}


@command("rm")
def rm(ctx):
    if ctx.args and ctx.args[0] == "save":
        return _rm_save(ctx, ctx.args[1:])
    flags, operands, bad = _split_flags(ctx.args, "rRfvi")
    if bad:
        ctx.err(f"rm: invalid option -- '{bad}'")
        return 1
    if not operands:
        ctx.err("rm: missing operand", "Usage: rm [-rf] <file>...")
        return 1
    recursive = bool(flags & {"r", "R"})
    status = 0
    for target in operands:
        abs_target = ctx.fs.abspath(target)
        if recursive and (abs_target in _PROTECTED or target in ("*", "/*")):
            ctx.out(Styled.plain("ERROR: Cannot delete bullets. They multiply too fast!", "error"))
            ctx.achieve("destructive")
            return 1
        if ctx.fs.is_directory_path(target):
            if not recursive:
                ctx.err(f"rm: cannot remove '{target}': Is a directory")
                status = 1
                continue
            ok, error = ctx.fs.delete_directory_recursive(target)
        else:
            if not ctx.fs.file_exists(target):
                if "f" not in flags:
                    ctx.err(f"rm: cannot remove '{target}': No such file or directory")
                    status = 1
                continue
            ok, error = ctx.fs.delete_file(target)
        if not ok:
            ctx.err(f"rm: {error}")
            status = 1
        elif "v" in flags:
            ctx.out(f"removed '{target}'")
    ctx.shell.save_filesystem()
    return status


def _rm_save(ctx, opts: list[str]):
    save = ctx.save
    fs = ctx.fs
    if not opts:
        save.reset_save()
        fs.reset_to_defaults()
        ctx.out(Styled.plain("Save data and filesystem reset. Starting fresh.", "warn"))
        ctx.achieve("fresh_start")
    elif opts == ["--filesystem"]:
        save.reset_filesystem()
        fs.reset_to_defaults()
        ctx.out("Filesystem reset. Stats and other data preserved.")
    elif opts == ["--filesystem-keep-files"]:
        save.reset_filesystem()
        fs.reset_filesystem_keep_user_files()
        ctx.shell.save_filesystem()
        ctx.out("Filesystem reset. Your files were moved to ~.")
    elif opts == ["--stats"]:
        save.reset_stats()
        ctx.out("Statistics reset. Filesystem and other data preserved.")
    elif len(opts) == 2 and opts[0] == "--dir":
        ok, error = fs.reset_directory(opts[1])
        if not ok:
            ctx.err(f"rm save: {error}")
            return 1
        ctx.shell.save_filesystem()
        ctx.out(f"Directory '{opts[1]}' reset to its default state.")
    else:
        ctx.err("Usage: rm save [--filesystem | --filesystem-keep-files | --stats | --dir <path>]")
        return 1
    return 0


@command("mkdir")
def mkdir(ctx):
    flags, operands, _ = _split_flags(ctx.args, "pv")
    if not operands:
        ctx.err("mkdir: missing operand", "Usage: mkdir [-p] <directory>")
        return 1
    status = 0
    for target in operands:
        if "p" in flags:
            parts = ctx.fs.normalize(target)
            for i in range(1, len(parts) + 1):
                sub = "/" + "/".join(parts[:i])
                if not ctx.fs.is_directory_path(sub):
                    ok, error = ctx.fs.create_directory(sub)
                    if not ok:
                        ctx.err(f"mkdir: {error}")
                        status = 1
                        break
            continue
        if ctx.fs.is_directory_path(target) or ctx.fs.file_exists(target):
            ctx.err(f"mkdir: cannot create directory '{target}': File exists")
            status = 1
            continue
        ok, error = ctx.fs.create_directory(target)
        if not ok:
            ctx.err(f"mkdir: {error}")
            status = 1
    ctx.shell.save_filesystem()
    return status


@command("rmdir")
def rmdir(ctx):
    if not ctx.args:
        ctx.err("rmdir: missing operand")
        return 1
    status = 0
    for target in ctx.args:
        ok, error = ctx.fs.delete_directory(target.rstrip("/"))
        if not ok:
            ctx.err(f"rmdir: failed to remove '{target}': {error}")
            status = 1
    ctx.shell.save_filesystem()
    return status


@command("touch")
def touch(ctx):
    if not ctx.args:
        ctx.err("touch: missing file operand")
        return 1
    status = 0
    for target in ctx.args:
        if ctx.fs.file_exists(target) or ctx.fs.is_directory_path(target):
            ctx.fs._update_timestamp(ctx.fs.abspath(target), "modify")
            continue
        ok, error = ctx.fs.create_file(target)
        if not ok:
            ctx.err(f"touch: {error}")
            status = 1
    ctx.shell.save_filesystem()
    return status


@command("chmod")
def chmod(ctx):
    operands = [a for a in ctx.args if a not in ("-R", "-v")]
    if len(operands) < 2:
        ctx.err("chmod: missing operand", "Usage: chmod <mode> <file>   (e.g. 755, +x, u+rw, go-w)")
        return 1
    mode, targets = operands[0], operands[1:]
    status = 0
    for target in targets:
        ok, error = ctx.fs.set_permissions(target, mode)
        if not ok:
            ctx.err(error)
            status = 1
    ctx.shell.save_filesystem()
    return status


@command("stat")
def stat(ctx):
    if not ctx.args:
        ctx.err("stat: missing operand")
        return 1
    fs = ctx.fs
    status = 0
    for target in ctx.args:
        is_dir = fs.is_directory_path(target)
        if not is_dir and not fs.file_exists(target):
            ctx.err(f"stat: cannot stat '{target}': No such file or directory")
            status = 1
            continue
        abspath = fs.abspath(target)
        if is_dir:
            parent, name = abspath.rsplit("/", 1) if abspath != "/" else ("", "")
            saved = fs.current_path[:]
            fs.current_path = fs.normalize(parent or "/")
            perms = fs.get_permissions(name) if name else "rwxr-xr-x"
            owner = fs.get_file_owner(name) if name else "root"
            fs.current_path = saved
            size = 4096
        else:
            perms = fs.get_permissions(target)
            owner = fs.get_file_owner(target)
            size = file_size(fs, target)
        stamps = {k: fs._get_timestamp(abspath, k) for k in ("access", "modify", "change")}
        fs._update_timestamp(abspath, "access")
        inode = sum(ord(c) * (i + 1) for i, c in enumerate(abspath)) % 900000 + 1000
        ctx.out(
            f"  File: {target}",
            f"  Size: {size:<12} Blocks: {(size + 511) // 512:<10} IO Block: 4096   "
            f"{'directory' if is_dir else 'regular file'}",
            f"Device: 801h/2049d      Inode: {inode:<8} Links: 1",
            f"Access: ({'d' if is_dir else '-'}{_perm_string(perms)})  Uid: ({owner})   Gid: (users)",
            f"Access: {stamps['access'].replace('T', ' ')}",
            f"Modify: {stamps['modify'].replace('T', ' ')}",
            f"Change: {stamps['change'].replace('T', ' ')}",
        )
    return status


_FILE_TYPES = {
    "py": "Python script, ASCII text executable",
    "txt": "ASCII text",
    "md": "UTF-8 Unicode text, Markdown document",
    "dat": "data",
    "log": "ASCII text, log file",
    "conf": "ASCII text, configuration file",
    "service": "systemd unit file, ASCII text",
    "sh": "Bourne-Again shell script, ASCII text executable",
    "json": "JSON data",
    "bin": "data (probably vibes)",
}


@command("file")
def file_cmd(ctx):
    if not ctx.args:
        ctx.err("file: missing operand")
        return 1
    for target in ctx.args:
        if ctx.fs.is_directory_path(target):
            ctx.out(f"{target}: directory")
            continue
        if not ctx.fs.file_exists(target):
            ctx.out(f"{target}: cannot open (No such file or directory)")
            continue
        base = target.rsplit("/", 1)[-1]
        ext = base.rsplit(".", 1)[-1] if "." in base.lstrip(".") else ""
        kind = _FILE_TYPES.get(ext, "ASCII text")
        ok, content = ctx.fs.read_file(target)
        if ok and content and str(content[0]).startswith("#!"):
            kind = "script, " + kind
        if ok and content and all(re.fullmatch(r"[A-Za-z0-9+/=]+", str(x)) for x in content) and len(content) > 1:
            kind = "ASCII text (looks like base64...)"
        if ok and not content:
            kind = "empty"
        ctx.out(f"{target}: {kind}")


@command("du")
def du(ctx):
    root = ctx.args[-1] if ctx.args and not ctx.args[-1].startswith("-") else "."
    if not ctx.fs.is_directory_path(root):
        ctx.err(f"du: cannot access '{root}': No such file or directory")
        return 1
    total = 0
    for dirpath, _dirs, files in ctx.fs.walk_directory(root):
        total += sum(file_size(ctx.fs, f"{dirpath.rstrip('/')}/{f}") for f in files)
    ctx.out(f"{max(1, (total + 1023) // 1024)}K\t{root}")
