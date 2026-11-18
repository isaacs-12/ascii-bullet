"""
Sandboxed Python script execution for the in-game `python` command.

Scripts are compiled with RestrictedPython and run against a virtual `os`
module and `open()` that only touch the game's VirtualFileSystem.
"""

from __future__ import annotations

import operator
import signal
import threading
import warnings
from collections.abc import Callable

from RestrictedPython import compile_restricted_exec, limited_builtins, utility_builtins
from RestrictedPython.Guards import (
    full_write_guard,
    guarded_iter_unpack_sequence,
    guarded_unpack_sequence,
    safe_builtins,
    safer_getattr,
)
from RestrictedPython.PrintCollector import PrintCollector

from src.unix.virtual_python.virtual_file import VirtualFile
from src.unix.virtual_python.virtual_os import StatResult, VirtualOS, VirtualOSPath


class ScriptTimeoutError(Exception):
    """Raised when a script exceeds its time budget."""


# Pure, side-effect free builtins that RestrictedPython's safe set omits.
_EXTRA_BUILTINS = {
    name: __builtins__[name] if isinstance(__builtins__, dict) else getattr(__builtins__, name)
    for name in (
        "all", "any", "dict", "enumerate", "filter", "format", "iter", "map", "max",
        "min", "next", "reversed", "sorted", "sum", "zip", "Exception", "KeyError",
        "IndexError", "StopIteration", "ZeroDivisionError",
    )
}

_INPLACE_OPS: dict[str, Callable] = {
    "+=": operator.iadd, "-=": operator.isub, "*=": operator.imul, "/=": operator.itruediv,
    "//=": operator.ifloordiv, "%=": operator.imod, "**=": operator.ipow,
    "<<=": operator.ilshift, ">>=": operator.irshift, "&=": operator.iand,
    "^=": operator.ixor, "|=": operator.ior,
}


def _inplacevar(op: str, x, y):
    func = _INPLACE_OPS.get(op)
    if func is None:
        raise SyntaxError(f"Unsupported in-place operator {op}")
    return func(x, y)


def _write_guard(obj):
    """Allow attribute writes on instances of classes the script defined itself."""
    if not isinstance(obj, type) and type(obj).__module__ == "__main__":
        return obj
    return full_write_guard(obj)


def _make_streaming_print(output_callback: Callable[[str], None]):
    """A PrintCollector that forwards completed lines immediately.

    The stock collector buffers into a per-function local, so prints inside
    functions were silently dropped. This one streams every line out.
    """

    class StreamingPrint(PrintCollector):
        _pending = [""]

        def write(self, text: str) -> None:
            buf = StreamingPrint._pending[0] + text
            *lines, rest = buf.split("\n")
            for line in lines:
                output_callback(line)
            StreamingPrint._pending[0] = rest

        @classmethod
        def flush_pending(cls) -> None:
            if cls._pending[0]:
                output_callback(cls._pending[0])
                cls._pending[0] = ""

    return StreamingPrint


class ScriptExecutor:
    """Executes Python scripts in a restricted environment."""

    MAX_EXECUTION_TIME = 5  # seconds

    def __init__(self):
        self.output_lines: list[str] = []

    @staticmethod
    def _timeout_handler(signum, frame):
        raise ScriptTimeoutError("Script execution timed out")

    def _get_safe_globals(self, filesystem, output_callback, save_callback):
        def safe_open(filename, mode="r", *args, **kwargs):
            return VirtualFile(filesystem, filename, mode, save_callback)

        virtual_os = VirtualOS(filesystem, save_callback)

        def custom_getattr(obj, name, default=None):
            # Our virtual objects are safe by construction; everything else
            # goes through RestrictedPython's guard.
            if isinstance(obj, (VirtualOS, VirtualOSPath, VirtualFile, StatResult)):
                if name.startswith("_"):
                    raise AttributeError(name)
                return getattr(obj, name)
            return safer_getattr(obj, name, default)

        builtins = {
            **safe_builtins,
            **limited_builtins,
            **utility_builtins,
            **_EXTRA_BUILTINS,
            "open": safe_open,
            "FileNotFoundError": FileNotFoundError,
            "FileExistsError": FileExistsError,
            "OSError": OSError,
            "PermissionError": PermissionError,
            "ValueError": ValueError,
            "TypeError": TypeError,
        }

        modules = {"os": virtual_os, "os.path": virtual_os, "math": utility_builtins["math"],
                   "random": utility_builtins["random"], "string": utility_builtins["string"]}

        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in modules:
                return modules[name]
            raise ImportError(f"No module named '{name}' (this sandbox only has os, math, random, string)")

        builtins["__import__"] = safe_import
        printer = _make_streaming_print(output_callback)
        safe_globals = {
            "__builtins__": builtins,
            "__name__": "__main__",
            "__metaclass__": type,
            "_getattr_": custom_getattr,
            "_getitem_": operator.getitem,
            "_getiter_": iter,
            "_write_": _write_guard,
            "_inplacevar_": _inplacevar,
            "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
            "_unpack_sequence_": guarded_unpack_sequence,
            "_print_": printer,
            "os": virtual_os,
        }
        return safe_globals, printer

    def execute(self, code, filesystem, output_callback, save_callback=None):
        """Run ``code`` (str or list of lines). Returns (success, error_message)."""
        if isinstance(code, list):
            code = "\n".join(str(line) for line in code)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            try:
                result = compile_restricted_exec(code, filename="<script>")
            except SyntaxError as e:
                return False, f"Syntax error: {e}"
        if result.errors:
            return False, "Compilation error:\n" + "\n".join(result.errors)

        safe_globals, printer = self._get_safe_globals(filesystem, output_callback, save_callback)

        use_alarm = hasattr(signal, "SIGALRM") and threading.current_thread() is threading.main_thread()
        if use_alarm:
            old_handler = signal.signal(signal.SIGALRM, self._timeout_handler)
            signal.alarm(self.MAX_EXECUTION_TIME)
        try:
            exec(result.code, safe_globals)
            return True, None
        except ScriptTimeoutError as e:
            return False, str(e)
        except SystemExit:
            return False, "Script attempted to exit"
        except Exception as e:  # noqa: BLE001 - surfaced to the player
            return False, f"Runtime error: {type(e).__name__}: {e}"
        finally:
            printer.flush_pending()
            if use_alarm:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
