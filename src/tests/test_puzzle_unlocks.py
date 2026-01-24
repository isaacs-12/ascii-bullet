"""
Unit tests for the puzzle/achievement unlock system.

Ensures that:
- Minesweeper puzzle: solved when .node_1_2 and .node_2_0 are deleted, others remain.
- Set puzzle: solved when card_1/2/3.dat perms are all same, or rwx------/---rwx---/------rwx.
- Dependency puzzle: solved when systemctl is fixed and cooler.service.d/override.conf contains Conflicts=laser.service.
- check_puzzles() unlocks games and returns messages only when conditions are met.
- get_unlocked_game_help_lines() returns help only for unlocked games.
"""

import unittest
from src.unix.filesystem import VirtualFileSystem
from src.core.puzzle_system import (
    check_puzzles,
    get_unlocked_game_help_lines,
    _check_minesweeper,
    _check_set,
    _check_dependency_puzzle,
    MINESWEEPER_DIR,
    SET_DIR,
    UNLOCKABLE_HELP,
)


class FakeSaveSystem:
    """Minimal save system for testing; no disk I/O."""

    def __init__(self):
        self.data = {"unlocked_games": []}

    def is_game_unlocked(self, game_key):
        return game_key in self.data.get("unlocked_games", [])

    def unlock_game(self, game_key):
        u = self.data.get("unlocked_games", [])
        if game_key not in u:
            self.data["unlocked_games"] = list(u) + [game_key]


class TestMinesweeperPuzzle(unittest.TestCase):
    def setUp(self):
        self.fs = VirtualFileSystem()
        self.fs.change_directory(MINESWEEPER_DIR)

    def test_not_solved_when_nothing_deleted(self):
        self.assertFalse(_check_minesweeper(self.fs))

    def test_not_solved_when_only_one_must_delete_removed(self):
        self.fs.delete_file(".node_1_2")
        self.assertFalse(_check_minesweeper(self.fs))

    def test_not_solved_when_both_must_delete_but_extra_deleted(self):
        self.fs.delete_file(".node_1_2")
        self.fs.delete_file(".node_2_0")
        self.fs.delete_file(".node_0_0")
        self.assertFalse(_check_minesweeper(self.fs))

    def test_solved_when_exactly_must_delete_removed_and_rest_remain(self):
        self.fs.delete_file(".node_1_2")
        self.fs.delete_file(".node_2_0")
        self.assertTrue(_check_minesweeper(self.fs))

    def test_check_puzzles_rm_unlocks_minesweeper_and_returns_message(self):
        save = FakeSaveSystem()
        self.fs.delete_file(".node_1_2")
        self.fs.delete_file(".node_2_0")

        out = check_puzzles(self.fs, save, "rm")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][0], "minesweeper")
        self.assertIn("minesweeper", out[0][1])
        self.assertTrue(save.is_game_unlocked("minesweeper"))

    def test_check_puzzles_rm_does_not_unlock_if_already_unlocked(self):
        save = FakeSaveSystem()
        save.unlock_game("minesweeper")
        self.fs.delete_file(".node_1_2")
        self.fs.delete_file(".node_2_0")

        out = check_puzzles(self.fs, save, "rm")
        self.assertEqual(len(out), 0)
        self.assertTrue(save.is_game_unlocked("minesweeper"))

    def test_check_puzzles_chmod_trigger_does_not_run_minesweeper(self):
        save = FakeSaveSystem()
        self.fs.delete_file(".node_1_2")
        self.fs.delete_file(".node_2_0")

        out = check_puzzles(self.fs, save, "chmod")
        self.assertEqual(len(out), 0)
        self.assertFalse(save.is_game_unlocked("minesweeper"))


class TestSetPuzzle(unittest.TestCase):
    def setUp(self):
        self.fs = VirtualFileSystem()
        self.fs.change_directory(SET_DIR)

    def test_not_solved_with_default_perms(self):
        # Default: rwx------, rwx------, ------rwx — not all same, not the three triplets
        self.assertFalse(_check_set(self.fs))

    def test_solved_when_all_three_perms_same(self):
        self.fs.set_permissions("card_1.dat", "rwxrwxrwx")
        self.fs.set_permissions("card_2.dat", "rwxrwxrwx")
        self.fs.set_permissions("card_3.dat", "rwxrwxrwx")
        self.assertTrue(_check_set(self.fs))

    def test_solved_when_perms_are_triplets_rwx_blank_blank_etc(self):
        self.fs.set_permissions("card_1.dat", "rwx------")
        self.fs.set_permissions("card_2.dat", "---rwx---")
        self.fs.set_permissions("card_3.dat", "------rwx")
        self.assertTrue(_check_set(self.fs))

    def test_solved_when_triplets_in_different_order(self):
        self.fs.set_permissions("card_1.dat", "------rwx")
        self.fs.set_permissions("card_2.dat", "rwx------")
        self.fs.set_permissions("card_3.dat", "---rwx---")
        self.assertTrue(_check_set(self.fs))

    def test_check_puzzles_chmod_unlocks_set_and_returns_message(self):
        save = FakeSaveSystem()
        self.fs.set_permissions("card_1.dat", "rwx------")
        self.fs.set_permissions("card_2.dat", "---rwx---")
        self.fs.set_permissions("card_3.dat", "------rwx")

        out = check_puzzles(self.fs, save, "chmod")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][0], "set")
        self.assertIn("set", out[0][1])
        self.assertTrue(save.is_game_unlocked("set"))

    def test_check_puzzles_rm_trigger_does_not_run_set(self):
        save = FakeSaveSystem()
        self.fs.set_permissions("card_1.dat", "rwx------")
        self.fs.set_permissions("card_2.dat", "---rwx---")
        self.fs.set_permissions("card_3.dat", "------rwx")

        out = check_puzzles(self.fs, save, "rm")
        self.assertEqual(len(out), 0)
        self.assertFalse(save.is_game_unlocked("set"))


class TestDependencyPuzzle(unittest.TestCase):
    def setUp(self):
        self.fs = VirtualFileSystem()

    def test_not_solved_when_systemctl_not_available(self):
        """Dependency puzzle not solved if systemctl hasn't been moved to /bin"""
        self.assertFalse(_check_dependency_puzzle(self.fs))

    def test_not_solved_when_cooler_override_missing(self):
        """Dependency puzzle not solved if cooler.service.d/override.conf doesn't exist"""
        # Move systemctl to /bin to make it available
        self.fs.set_user('root')
        self.fs.change_directory("/usr/local/deprecated")
        success, _ = self.fs.move_file("sys_control.py", "/bin/systemctl")
        self.assertTrue(success, "Should be able to move systemctl to /bin")
        
        # Make it executable
        self.fs.change_directory("/bin")
        self.fs.set_permissions("systemctl", "rwxr-xr-x")
        
        # Go back to root to check - should fail without override
        self.fs.change_directory("/")
        self.assertFalse(_check_dependency_puzzle(self.fs))

    def test_solved_when_cooler_overrides_laser(self):
        """Dependency puzzle solved when cooler.service conflicts with laser.service"""
        # Move systemctl to /bin
        self.fs.set_user('root')
        self.fs.change_directory("/usr/local/deprecated")
        success, _ = self.fs.move_file("sys_control.py", "/bin/systemctl")
        self.assertTrue(success)
        
        # Make it executable
        self.fs.change_directory("/bin")
        self.fs.set_permissions("systemctl", "rwxr-xr-x")
        
        # Create cooler.service.d directory and override
        self.fs.change_directory("/etc/systemd/system")
        self.fs.create_directory("cooler.service.d")
        self.fs.change_directory("cooler.service.d")
        self.fs.create_file("override.conf", "[Unit]\nConflicts=laser.service\n")
        
        # Check root directory for puzzle completion
        self.fs.change_directory("/")
        self.assertTrue(_check_dependency_puzzle(self.fs))

    def test_check_puzzles_systemctl_unlocks_oregon_trail(self):
        """check_puzzles() unlocks oregon_trail when dependency puzzle is solved"""
        save = FakeSaveSystem()
        
        # Move systemctl to /bin
        self.fs.set_user('root')
        self.fs.change_directory("/usr/local/deprecated")
        self.fs.move_file("sys_control.py", "/bin/systemctl")
        
        # Make it executable
        self.fs.change_directory("/bin")
        self.fs.set_permissions("systemctl", "rwxr-xr-x")
        
        # Create cooler.service.d/override.conf
        self.fs.change_directory("/etc/systemd/system")
        self.fs.create_directory("cooler.service.d")
        self.fs.change_directory("cooler.service.d")
        self.fs.create_file("override.conf", "[Unit]\nConflicts=laser.service\n")
        
        # Go to root and check puzzles with systemctl trigger
        self.fs.change_directory("/")
        out = check_puzzles(self.fs, save, "systemctl")
        
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][0], "oregon_trail")
        self.assertIn("oregon_trail", out[0][1])
        self.assertTrue(save.is_game_unlocked("oregon_trail"))


class TestGetUnlockedGameHelpLines(unittest.TestCase):
    def test_returns_empty_when_none_unlocked(self):
        save = FakeSaveSystem()
        self.assertEqual(get_unlocked_game_help_lines(save), [])

    def test_returns_minesweeper_line_only_when_minesweeper_unlocked(self):
        save = FakeSaveSystem()
        save.unlock_game("minesweeper")
        lines = get_unlocked_game_help_lines(save)
        self.assertEqual(lines, [UNLOCKABLE_HELP["minesweeper"]])

    def test_returns_all_unlocked_games(self):
        save = FakeSaveSystem()
        save.unlock_game("minesweeper")
        save.unlock_game("set")
        save.unlock_game("oregon_trail")
        lines = get_unlocked_game_help_lines(save)
        self.assertIn(UNLOCKABLE_HELP["minesweeper"], lines)
        self.assertIn(UNLOCKABLE_HELP["set"], lines)
        self.assertIn(UNLOCKABLE_HELP["oregon_trail"], lines)
        self.assertEqual(len(lines), 3)
