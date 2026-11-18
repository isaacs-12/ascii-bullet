"""
Persistent save data.

Save files are user-specific and live outside the repo:

- Development:  ~/.ascii-bullet/save.json
- Built game:   ~/.ascii-bullet-release/save.json
- Override:     $ASCII_BULLET_SAVE_DIR/save.json  (used by tests and CI)

Writes are atomic (temp file + rename) so a crash mid-save can't corrupt
progress. Older or partial save files are deep-merged over the current
defaults, so new keys never raise KeyError on load.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

SAVE_VERSION = "0.2.0"
SAVE_DIR_ENV = "ASCII_BULLET_SAVE_DIR"
MAX_HIGH_SCORES = 10
MAX_HISTORY = 200

_DEFAULT_STATS: dict[str, Any] = {
    "bullets_dodged": 0,
    "closest_call": 999,
    "enemies_depleted": 0,
    "grazes": 0,
    "bombs_used": 0,
    "bosses_defeated": 0,
    "best_wave": 0,
    "set_games_played": 0,
    "set_games_won": 0,
    "set_games_lost": 0,
    "total_sets_found": 0,
    "best_set_score": 0,
    "asteroids_games_played": 0,
    "asteroids_best_score": 0,
    "asteroids_total_score": 0,
    "asteroids_highest_stage": 0,
    "ai_prompts": 0,
    "total_playtime_seconds": 0,
    "bullet_hell_playtime_seconds": 0,
    "set_game_playtime_seconds": 0,
    "asteroids_playtime_seconds": 0,
    "oregon_trail_playtime_seconds": 0,
    "minesweeper_playtime_seconds": 0,
}


def _deep_merge(defaults: dict, loaded: dict) -> dict:
    """Return defaults overlaid with loaded values, recursing into dicts."""
    merged = copy.deepcopy(defaults)
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def default_save_dir() -> Path:
    override = os.environ.get(SAVE_DIR_ENV)
    if override:
        return Path(override)
    name = ".ascii-bullet-release" if getattr(sys, "frozen", False) else ".ascii-bullet"
    return Path.home() / name


class SaveSystem:
    """Manages saving and loading game data."""

    def __init__(self, save_dir: Path | str | None = None):
        self.save_dir = Path(save_dir) if save_dir else default_save_dir()
        self.save_file = self.save_dir / "save.json"
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self._existed_at_start = self.save_file.exists()
        self.data = self._load()

    # ------------------------------------------------------------------ io
    def _load(self) -> dict:
        if not self.save_file.exists():
            return self._default_save_data()
        try:
            with open(self.save_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            # Corrupted save: keep a copy for forensics and start fresh.
            try:
                self.save_file.replace(self.save_file.with_suffix(".corrupt.json"))
            except OSError:
                pass
            return self._default_save_data()
        if not isinstance(loaded, dict):
            return self._default_save_data()
        data = _deep_merge(self._default_save_data(), loaded)
        data["version"] = SAVE_VERSION
        return data

    @staticmethod
    def _default_save_data() -> dict:
        now = datetime.now().isoformat()
        return {
            "version": SAVE_VERSION,
            "created": now,
            "last_played": now,
            "high_scores": [],  # [{score, time, date, wave}]
            "total_games_played": 0,
            "total_time_survived": 0,
            # Achievement / secret IDs (kept under the legacy key for old saves)
            "secret_commands_found": [],
            "installed_packages": [],
            "virus_killed": False,
            "unlocked_games": [],
            "intro_shown": False,
            "save_prompt_shown": False,
            "filesystem_explored": {"directories_visited": [], "files_read": []},
            "stats": copy.deepcopy(_DEFAULT_STATS),
            "settings": {"crt": True, "screen_shake": True},
            "filesystem": None,
            "command_history": [],
            "systemd_states": {},
            "systemd_enabled": [],
            "bullet_hell": {"checkpoint_wave": 0},
            "flags": {},
        }

    def save(self) -> bool:
        """Atomically write save data to disk."""
        self.data["last_played"] = datetime.now().isoformat()
        try:
            fd, tmp = tempfile.mkstemp(dir=self.save_dir, prefix=".save-", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            os.replace(tmp, self.save_file)
            return True
        except (OSError, TypeError, ValueError):
            try:
                os.unlink(tmp)  # type: ignore[possibly-undefined]
            except (OSError, UnboundLocalError):
                pass
            return False

    def export_save(self, filepath) -> bool:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            return True
        except OSError:
            return False

    def get_save_location(self) -> str:
        return str(self.save_file)

    # ------------------------------------------------------------- scores
    def add_score(self, score: int, time_survived: int, wave: int = 0) -> None:
        entry = {
            "score": int(score),
            "time": int(time_survived),
            "wave": int(wave),
            "date": datetime.now().isoformat(),
        }
        scores = self.data["high_scores"]
        scores.append(entry)
        scores.sort(key=lambda x: x["score"], reverse=True)
        del scores[MAX_HIGH_SCORES:]
        self.data["total_games_played"] += 1
        self.data["total_time_survived"] += int(time_survived)
        self.save()

    def get_high_scores(self, limit: int = MAX_HIGH_SCORES) -> list:
        return self.data["high_scores"][:limit]

    def is_high_score(self, score: int) -> bool:
        scores = self.data["high_scores"]
        return score > 0 and (len(scores) < MAX_HIGH_SCORES or score > scores[-1]["score"])

    def get_best_score(self) -> int:
        scores = self.data["high_scores"]
        return scores[0]["score"] if scores else 0

    # ---------------------------------------------- achievements / secrets
    def add_secret_found(self, secret_id: str) -> bool:
        """Record an achievement. Returns True if newly unlocked."""
        found = self.data["secret_commands_found"]
        if secret_id in found:
            return False
        found.append(secret_id)
        self.save()
        return True

    def has_secret(self, secret_id: str) -> bool:
        return secret_id in self.data["secret_commands_found"]

    def get_secrets_found(self) -> list:
        return self.data["secret_commands_found"]

    def get_secret_count(self) -> int:
        return len(self.data["secret_commands_found"])

    # ----------------------------------------------------------- packages
    def install_package(self, package_name: str) -> bool:
        pkgs = self.data["installed_packages"]
        if package_name in pkgs:
            return False
        pkgs.append(package_name)
        self.save()
        return True

    def is_package_installed(self, package_name: str) -> bool:
        return package_name in self.data["installed_packages"]

    def get_installed_packages(self) -> list:
        return self.data["installed_packages"]

    # ------------------------------------------------------ progress flags
    def mark_virus_killed(self) -> None:
        self.data["virus_killed"] = True
        self.save()

    def is_virus_killed(self) -> bool:
        return bool(self.data.get("virus_killed", False))

    def is_game_unlocked(self, game_key: str) -> bool:
        return game_key in self.data["unlocked_games"]

    def unlock_game(self, game_key: str) -> None:
        if game_key not in self.data["unlocked_games"]:
            self.data["unlocked_games"].append(game_key)
            self.save()

    def get_flag(self, name: str, default: Any = None) -> Any:
        return self.data["flags"].get(name, default)

    def set_flag(self, name: str, value: Any) -> None:
        self.data["flags"][name] = value
        self.save()

    # -------------------------------------------------------------- intro
    def has_intro_been_shown(self) -> bool:
        return bool(self.data.get("intro_shown", False))

    def mark_intro_shown(self) -> None:
        self.data["intro_shown"] = True
        self.save()

    def should_prompt_for_existing_save(self) -> bool:
        """Built games ask once whether to keep a save found on first launch."""
        if not getattr(sys, "frozen", False):
            return False
        return self._existed_at_start and not self.data.get("save_prompt_shown", False)

    def mark_save_prompt_shown(self) -> None:
        self.data["save_prompt_shown"] = True
        self.save()

    def has_existing_save(self) -> bool:
        return self.save_file.exists()

    # -------------------------------------------------------- exploration
    def mark_directory_visited(self, path: str) -> None:
        visited = self.data["filesystem_explored"]["directories_visited"]
        if path not in visited:
            visited.append(path)
            self.save()

    def mark_file_read(self, filepath: str) -> None:
        read = self.data["filesystem_explored"]["files_read"]
        if filepath not in read:
            read.append(filepath)
            self.save()

    def get_exploration_stats(self) -> dict:
        explored = self.data["filesystem_explored"]
        return {
            "dirs_visited": len(explored["directories_visited"]),
            "files_read": len(explored["files_read"]),
        }

    # -------------------------------------------------------------- stats
    def update_stat(self, stat_name: str, value) -> None:
        stats = self.data["stats"]
        if stat_name == "closest_call":
            stats[stat_name] = min(stats.get(stat_name, 999), value)
        elif stat_name in ("best_wave",):
            stats[stat_name] = max(stats.get(stat_name, 0), value)
        else:
            stats[stat_name] = stats.get(stat_name, 0) + value
        self.save()

    def record_set_game(self, player_sets: int, computer_sets: int, won: bool) -> None:
        stats = self.data["stats"]
        stats["set_games_played"] += 1
        stats["set_games_won" if won else "set_games_lost"] += 1
        stats["total_sets_found"] += player_sets
        stats["best_set_score"] = max(stats["best_set_score"], player_sets)
        self.save()

    def record_asteroids_game(self, score: int, stage: int) -> None:
        stats = self.data["stats"]
        stats["asteroids_games_played"] += 1
        stats["asteroids_total_score"] += score
        stats["asteroids_best_score"] = max(stats["asteroids_best_score"], score)
        stats["asteroids_highest_stage"] = max(stats["asteroids_highest_stage"], stage)
        self.save()

    def add_playtime(self, seconds: float, game_type: str = "total") -> None:
        """Add playtime.

        ``total`` is wall-clock time tracked by the main loop; per-game buckets
        are tracked separately and do NOT add to total (that double counted).
        """
        if seconds <= 0:
            return
        key = f"{game_type}_playtime_seconds"
        stats = self.data["stats"]
        stats[key] = stats.get(key, 0) + seconds
        self.save()

    def get_stat(self, stat_name: str):
        return self.data["stats"].get(stat_name, 0)

    def get_all_stats(self) -> dict:
        return self.data["stats"].copy()

    # ----------------------------------------------------------- settings
    def update_setting(self, setting_name: str, value) -> None:
        self.data["settings"][setting_name] = value
        self.save()

    def get_setting(self, setting_name: str, default=None):
        return self.data["settings"].get(setting_name, default)

    # --------------------------------------------------------- filesystem
    def save_filesystem(self, filesystem_state: dict) -> None:
        self.data["filesystem"] = filesystem_state
        self.save()

    def get_filesystem_state(self):
        return self.data.get("filesystem")

    # -------------------------------------------------------------- reset
    def reset_save(self) -> None:
        self.data = self._default_save_data()
        self.save()

    def reset_filesystem(self) -> None:
        self.data["filesystem"] = None
        self.save()

    def reset_stats(self) -> None:
        self.data["stats"] = copy.deepcopy(_DEFAULT_STATS)
        self.data["high_scores"] = []
        self.data["total_games_played"] = 0
        self.data["total_time_survived"] = 0
        self.data["bullet_hell"] = {"checkpoint_wave": 0}
        self.save()

    # -------------------------------------------------------- bullet hell
    def get_checkpoint_wave(self) -> int:
        return int(self.data["bullet_hell"].get("checkpoint_wave", 0))

    def set_checkpoint_wave(self, wave: int) -> None:
        current = self.get_checkpoint_wave()
        if wave > current:
            self.data["bullet_hell"]["checkpoint_wave"] = int(wave)
            self.save()

    # ------------------------------------------------------- oregon trail
    def save_oregon_trail(self, game_state) -> None:
        self.data.setdefault("oregon_trail", {})["game_state"] = game_state
        self.save()

    def load_oregon_trail(self):
        return self.data.get("oregon_trail", {}).get("game_state")

    def clear_oregon_trail(self) -> None:
        if "oregon_trail" in self.data:
            del self.data["oregon_trail"]
            self.save()

    # ---------------------------------------------------- command history
    def get_command_history(self, max_items: int = MAX_HISTORY) -> list:
        return self.data["command_history"][-max_items:]

    def save_command_history(self, command_history: list, max_items: int = MAX_HISTORY) -> None:
        self.data["command_history"] = list(command_history[-max_items:])
        self.save()

    # ------------------------------------------------------------ systemd
    def save_systemd_states(self, states: dict) -> None:
        self.data["systemd_states"] = states
        self.save()

    def get_systemd_states(self):
        return self.data.get("systemd_states")

    def save_systemd_enabled(self, enabled_services: list) -> None:
        self.data["systemd_enabled"] = enabled_services
        self.save()

    def get_systemd_enabled(self):
        return self.data.get("systemd_enabled")
