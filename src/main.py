"""Entry point: `python main.py`, `python -m src.main` or the `ascii-bullet` script."""

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def main() -> int:
    from src.core.game import Game
    from src.core.save_system import default_save_dir

    try:
        Game().run()
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception:  # noqa: BLE001 - last-resort crash reporter
        report = traceback.format_exc()
        crash_dir = default_save_dir()
        try:
            crash_dir.mkdir(parents=True, exist_ok=True)
            crash_file = crash_dir / f"crash-{datetime.now():%Y%m%d-%H%M%S}.log"
            crash_file.write_text(report, encoding="utf-8")
            print(f"BLTHLL crashed. Details written to {crash_file}", file=sys.stderr)
        except OSError:
            pass
        print(report, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
