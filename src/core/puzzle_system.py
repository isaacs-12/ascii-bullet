"""
Puzzle and achievement system for gated game unlocks.

Each puzzle defines:
- id: unique string
- unlocks: game key for 'start <game>' (e.g. 'minesweeper', 'set')
- trigger_on: list of command types that can satisfy this puzzle ('rm', 'chmod', ...)
- check(filesystem) -> bool

When a puzzle's check() returns True and the game is not yet unlocked, we unlock it
and can show a message. Main menu calls check_puzzles(filesystem, save_system, trigger)
after relevant commands (rm, chmod).
"""

# Paths (relative to filesystem root) for puzzle contexts
MINESWEEPER_DIR = "/home/pilot/blthll/games/minesweeper"
SET_DIR = "/home/pilot/blthll/games/set"

# Must be deleted for minesweeper puzzle; all other .node_* must remain
MINESWEEPER_MUST_DELETE = [".node_1_2", ".node_2_0"]
MINESWEEPER_MUST_REMAIN = [".node_0_0", ".node_0_1", ".node_0_2", ".node_1_0", ".node_1_1", ".node_2_1", ".node_2_2"]

SET_CARD_FILES = ["card_1.dat", "card_2.dat", "card_3.dat"]
# A permission "set": either all same, or these three (user/group/other each get rwx in exactly one file)
SET_PERM_TRIPLETS = {"rwx------", "---rwx---", "------rwx"}


def _normalize_perms(p):
    """Expand 3-char to 9-char if needed."""
    if not p or len(p) == 9:
        return p or ""
    if len(p) == 3:
        return p + p + p
    return p


def _check_minesweeper(filesystem):
    base = MINESWEEPER_DIR
    for f in MINESWEEPER_MUST_DELETE:
        path = f"{base}/{f}"
        if path not in filesystem.user_deleted_files:
            return False
    for f in MINESWEEPER_MUST_REMAIN:
        path = f"{base}/{f}"
        if path in filesystem.user_deleted_files:
            return False
    return True


def _check_set(filesystem):
    perms = []
    saved = filesystem.current_path[:]
    try:
        filesystem.current_path = [x for x in SET_DIR.strip("/").split("/") if x]
        for fn in SET_CARD_FILES:
            p = filesystem.get_permissions(fn)
            perms.append(_normalize_perms(p or ""))
    finally:
        filesystem.current_path = saved

    if len(perms) != 3 or any(len(p) != 9 for p in perms):
        return False
    # All same?
    if perms[0] == perms[1] == perms[2]:
        return True
    # Bit-masked different (rwx------, ---rwx---, ------rwx)?
    if set(perms) == SET_PERM_TRIPLETS:
        return True
    return False


# Registry: id -> { unlocks, trigger_on, check }
PUZZLES = [
    {
        "id": "minesweeper",
        "unlocks": "minesweeper",
        "trigger_on": ["rm"],
        "check": _check_minesweeper,
        "message": "Minesweeper unlocked! You can now run 'start minesweeper'.",
    },
    {
        "id": "set",
        "unlocks": "set",
        "trigger_on": ["chmod"],
        "check": _check_set,
        "message": "Set card game unlocked! You can now run 'start set'.",
    },
]

# Help line for each unlockable game (shown in help when unlocked)
UNLOCKABLE_HELP = {
    "minesweeper": "  start minesweeper - Launch Minesweeper",
    "set": "  start set   - Set card game",
}


def check_puzzles(filesystem, save_system, trigger):
    """
    Run puzzles that are triggered by `trigger` (e.g. 'rm', 'chmod').
    For any that pass and whose game is not yet unlocked, unlock the game and
    return a list of (game_key, message) for newly unlocked games.
    """
    newly = []
    for p in PUZZLES:
        if trigger not in p["trigger_on"]:
            continue
        if save_system.is_game_unlocked(p["unlocks"]):
            continue
        if not p["check"](filesystem):
            continue
        save_system.unlock_game(p["unlocks"])
        newly.append((p["unlocks"], p["message"]))
    return newly


def get_unlocked_game_help_lines(save_system):
    """Return help lines for each unlocked puzzle-gated game, for inclusion in help."""
    return [UNLOCKABLE_HELP[g] for g in UNLOCKABLE_HELP if save_system.is_game_unlocked(g)]
