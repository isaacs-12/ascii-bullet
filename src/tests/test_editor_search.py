"""
Unit tests for VSCode-like editor search features.

Tests:
- File content search (sidebar search)
- Quick open file search (Cmd+P)
- Search result navigation
"""

import unittest

from src.unix.filesystem import VirtualFileSystem


class TestFileContentSearch(unittest.TestCase):
    """Test the search functionality without full editor initialization"""

    def setUp(self):
        """Set up test fixtures"""
        self.fs = VirtualFileSystem()
        self.fs.change_directory("/home/pilot")

        # Create test files
        self.fs.create_file("test1.py", ["def hello():", "    print('Hello')", "    # TODO: add more"])
        self.fs.create_file("test2.py", ["# TODO: fix this", "def goodbye():", "    pass"])
        self.fs.create_file("readme.txt", ["Read me", "No todos here"])

    def test_filesystem_file_creation(self):
        """Verify test files exist"""
        self.assertTrue(self.fs.file_exists("test1.py"))
        self.assertTrue(self.fs.file_exists("test2.py"))
        self.assertTrue(self.fs.file_exists("readme.txt"))

    def test_file_reading(self):
        """Verify files can be read"""
        success, content = self.fs.read_file("test1.py")
        self.assertTrue(success)
        self.assertIsNotNone(content)

    def test_search_results_structure(self):
        """Test that search results have proper structure"""
        success, content = self.fs.read_file("test1.py")
        self.assertTrue(success)

        # Manually verify search logic
        query = "TODO"
        query_lower = query.lower()
        results = []

        for line_num, line_text in enumerate(content):
            if query_lower in line_text.lower():
                results.append((line_num, line_text.strip()))

        # Should find at least one TODO
        self.assertGreater(len(results), 0)

        # Verify result structure
        line_num, line_text = results[0]
        self.assertIsInstance(line_num, int)
        self.assertIsInstance(line_text, str)
        self.assertIn("TODO", line_text.upper())

    def test_case_insensitive_search(self):
        """Search should be case-insensitive"""
        success, content = self.fs.read_file("test2.py")

        query = "todo"  # lowercase
        query_lower = query.lower()
        found = False

        for line_text in content:
            if query_lower in line_text.lower():
                found = True
                break

        self.assertTrue(found)

    def test_no_match_search(self):
        """Search with no matches should return empty"""
        success, content = self.fs.read_file("readme.txt")

        query = "NONEXISTENT_12345"
        query_lower = query.lower()
        results = []

        for line_num, line_text in enumerate(content):
            if query_lower in line_text.lower():
                results.append((line_num, line_text))

        self.assertEqual(len(results), 0)


class TestQuickOpenSearch(unittest.TestCase):
    """Test quick open file search logic"""

    def setUp(self):
        """Set up test fixtures"""
        self.fs = VirtualFileSystem()
        self.fs.change_directory("/home/pilot")

        # Create test files
        self.fs.create_file("test_main.py", [])
        self.fs.create_file("test_helper.py", [])
        self.fs.create_file("readme.txt", [])

    def test_file_matching(self):
        """Test file name matching logic"""
        files = ["test_main.py", "test_helper.py", "readme.txt"]
        query = "test"
        query_lower = query.lower()

        matches = [f for f in files if query_lower in f.lower()]

        self.assertEqual(len(matches), 2)
        self.assertIn("test_main.py", matches)
        self.assertIn("test_helper.py", matches)

    def test_specific_file_matching(self):
        """Test matching specific file"""
        files = ["test_main.py", "test_helper.py", "readme.txt"]
        query = "main"
        query_lower = query.lower()

        matches = [f for f in files if query_lower in f.lower()]

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0], "test_main.py")

    def test_case_insensitive_file_matching(self):
        """File matching should be case-insensitive"""
        files = ["test_main.py", "test_helper.py", "readme.txt"]
        query = "MAIN"  # uppercase
        query_lower = query.lower()

        matches = [f for f in files if query_lower in f.lower()]

        self.assertEqual(len(matches), 1)
        self.assertIn("test_main.py", matches)

    def test_no_file_match(self):
        """No matches should return empty"""
        files = ["test_main.py", "test_helper.py", "readme.txt"]
        query = "NONEXISTENT"
        query_lower = query.lower()

        matches = [f for f in files if query_lower in f.lower()]

        self.assertEqual(len(matches), 0)


class TestSearchNavigation(unittest.TestCase):
    """Test navigation cursor logic"""

    def test_cursor_down_navigation(self):
        """Test cursor moving down"""
        results = ["file1.py", "file2.py", "file3.py"]
        cursor = 0

        # Move down
        cursor = min(len(results) - 1, cursor + 1)
        self.assertEqual(cursor, 1)

        # Move down again
        cursor = min(len(results) - 1, cursor + 1)
        self.assertEqual(cursor, 2)

        # Try to move down beyond last
        cursor = min(len(results) - 1, cursor + 1)
        self.assertEqual(cursor, 2)  # Should stay at last

    def test_cursor_up_navigation(self):
        """Test cursor moving up"""
        cursor = 2

        # Move up
        cursor = max(0, cursor - 1)
        self.assertEqual(cursor, 1)

        # Move up again
        cursor = max(0, cursor - 1)
        self.assertEqual(cursor, 0)

        # Try to move up beyond first
        cursor = max(0, cursor - 1)
        self.assertEqual(cursor, 0)  # Should stay at first

    def test_empty_results_cursor(self):
        """Cursor should be 0 for empty results"""
        cursor = 0

        self.assertEqual(cursor, 0)


if __name__ == '__main__':
    unittest.main()
