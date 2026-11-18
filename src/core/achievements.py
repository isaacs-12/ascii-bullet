"""
Achievements (a.k.a. secrets), defined in ``src/data/achievements.json``.

Each entry: ``id``, ``name``, ``description``, ``hidden`` and optional
declarative triggers ``on_command`` (command names) and ``on_read`` (absolute
file paths). Anything more involved unlocks from code via ``unlock(id)``.
Unlocked IDs persist through SaveSystem (legacy key ``secret_commands_found``).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "achievements.json"


@lru_cache(maxsize=1)
def load_achievements() -> tuple[dict, ...]:
    with open(DATA_FILE, encoding="utf-8") as f:
        return tuple(json.load(f))


def achievement_index() -> dict[str, dict]:
    return {a["id"]: a for a in load_achievements()}


class AchievementTracker:
    def __init__(self, save_system, on_unlock: Callable[[dict], None] | None = None):
        self.save = save_system
        self.on_unlock = on_unlock
        self.index = achievement_index()
        self._by_command: dict[str, list[str]] = {}
        self._by_read: dict[str, list[str]] = {}
        for a in load_achievements():
            for cmd in a.get("on_command", ()):
                self._by_command.setdefault(cmd, []).append(a["id"])
            for path in a.get("on_read", ()):
                self._by_read.setdefault(path, []).append(a["id"])

    def unlock(self, achievement_id: str) -> bool:
        """Unlock an achievement; returns True if it was new. Unknown IDs are ignored."""
        if achievement_id not in self.index:
            return False
        if not self.save.add_secret_found(achievement_id):
            return False
        if self.on_unlock:
            self.on_unlock(self.index[achievement_id])
        return True

    def on_command(self, name: str, args: list[str] | None = None) -> None:
        for aid in self._by_command.get(name, ()):
            self.unlock(aid)

    def on_read(self, abspath: str) -> None:
        for aid in self._by_read.get(abspath, ()):
            self.unlock(aid)

    def is_unlocked(self, achievement_id: str) -> bool:
        return self.save.has_secret(achievement_id)

    def summary(self) -> tuple[int, int]:
        found = sum(1 for a in self.index if self.save.has_secret(a))
        return found, len(self.index)
