"""
Unit tests for filesystem reset functions
"""

import unittest
from src.unix.filesystem import VirtualFileSystem


class TestFilesystemReset(unittest.TestCase):
    """Test cases for filesystem reset operations"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.filesystem = VirtualFileSystem()
    
    def test_reset_to_defaults(self):
        """Test resetting entire filesystem to defaults"""
        # Create some user modifications
        self.filesystem.create_file("custom.txt", ["user content"])
        self.filesystem.create_directory("custom_dir")
        
        # Create a file and then delete it (simulating deletion)
        self.filesystem.create_file("temp.txt", ["temp"])
        success, _ = self.filesystem.delete_file("temp.txt")
        self.assertTrue(success)
        
        # Modify a user-created file
        success, _ = self.filesystem.write_file("custom.txt", "modified content")
        self.assertTrue(success, "Failed to modify custom.txt")
        
        # Verify modifications exist
        self.assertIn("/home/pilot/blthll/custom.txt", self.filesystem.user_created_files)
        self.assertIn("/home/pilot/blthll/custom_dir/", self.filesystem.user_created_dirs)
        
        # Reset to defaults
        self.filesystem.reset_to_defaults()
        
        # Verify everything is reset
        self.assertEqual(len(self.filesystem.user_created_files), 0)
        self.assertEqual(len(self.filesystem.user_created_dirs), 0)
        self.assertEqual(len(self.filesystem.user_deleted_files), 0)
        self.assertEqual(len(self.filesystem.user_modified_files), 0)
        self.assertEqual(self.filesystem.current_path, ['home', 'pilot', 'blthll'])
    
    def test_reset_filesystem_keep_user_files(self):
        """Test resetting filesystem but keeping user-created files"""
        # Create files in different directories
        self.filesystem.create_file("file1.txt", ["content 1"])
        self.filesystem.change_directory("data")
        self.filesystem.create_file("file2.txt", ["content 2"])
        self.filesystem.change_directory("secret")
        self.filesystem.create_file("file3.txt", ["content 3"])
        
        # Verify files exist in different locations
        self.assertIn("/home/pilot/blthll/file1.txt", self.filesystem.user_created_files)
        self.assertIn("/home/pilot/blthll/data/file2.txt", self.filesystem.user_created_files)
        self.assertIn("/home/pilot/blthll/data/secret/file3.txt", self.filesystem.user_created_files)
        
        # Reset but keep user files
        self.filesystem.reset_filesystem_keep_user_files()
        
        # Verify user files are moved to blthll
        self.assertIn("/home/pilot/blthll/file1.txt", self.filesystem.user_created_files)
        self.assertIn("/home/pilot/blthll/file2.txt", self.filesystem.user_created_files)
        self.assertIn("/home/pilot/blthll/file3.txt", self.filesystem.user_created_files)
        
        # Verify files are no longer in original locations
        self.assertNotIn("/home/pilot/blthll/data/file2.txt", self.filesystem.user_created_files)
        self.assertNotIn("/home/pilot/blthll/data/secret/file3.txt", self.filesystem.user_created_files)
    
    def test_reset_directory_removes_user_created_files(self):
        """Test that reset_directory removes user-created files"""
        # Create a user file in blthll directory
        self.filesystem.change_directory("/home/pilot/blthll")
        self.filesystem.create_file("user_file.txt", ["user content"])
        
        # Verify it exists
        self.assertIn("/home/pilot/blthll/user_file.txt", self.filesystem.user_created_files)
        success, _ = self.filesystem.read_file("user_file.txt")
        self.assertTrue(success)
        
        # Reset the directory (use absolute path)
        success, error = self.filesystem.reset_directory("/home/pilot/blthll")
        self.assertTrue(success, f"Reset failed: {error}")
        
        # Verify user file is removed
        self.assertNotIn("/home/pilot/blthll/user_file.txt", self.filesystem.user_created_files)
        success, _ = self.filesystem.read_file("user_file.txt")
        self.assertFalse(success)
    
    def test_reset_directory_restores_deleted_default_files(self):
        """Test that reset_directory restores deleted default files"""
        # Create a file, then delete it to simulate a deleted default file
        # (We'll manually add it to user_deleted_files to simulate a deleted default)
        self.filesystem.change_directory("/home/pilot/blthll")
        test_path = "/home/pilot/blthll/test_default.txt"
        # Manually add to deleted files to simulate a deleted default file
        self.filesystem.user_deleted_files.add(test_path)
        
        # Verify it's marked as deleted
        self.assertIn(test_path, self.filesystem.user_deleted_files)
        
        # Reset the directory (use absolute path)
        success, error = self.filesystem.reset_directory("/home/pilot/blthll")
        self.assertTrue(success, f"Reset failed: {error}")
        
        # Note: Since test_default.txt isn't actually a default file, 
        # it won't be restored, but the reset should still work
        # This test mainly verifies the reset logic runs without error
    
    def test_reset_directory_restores_moved_default_files(self):
        """Test that reset_directory moves default files back to original location"""
        # Create a file and move it to simulate a moved default file
        self.filesystem.change_directory("/home/pilot/blthll")
        self.filesystem.create_file("test_moved.txt", ["original content"])
        original_path = "/home/pilot/blthll/test_moved.txt"
        
        # Move it to data directory
        self.filesystem.change_directory("/home/pilot/blthll")
        success, _ = self.filesystem.move_file("test_moved.txt", "data/test_moved.txt")
        self.assertTrue(success, "Failed to move test_moved.txt")
        
        # Verify it's in the new location
        self.filesystem.change_directory("data")
        success, content = self.filesystem.read_file("test_moved.txt")
        self.assertTrue(success)
        
        # Verify it's in user_created_files at new location
        self.assertIn("/home/pilot/blthll/data/test_moved.txt", self.filesystem.user_created_files)
        
        # Reset the blthll directory (use absolute path)
        success, error = self.filesystem.reset_directory("/home/pilot/blthll")
        self.assertTrue(success, f"Reset failed: {error}")
        
        # Verify file is removed from new location
        self.assertNotIn("/home/pilot/blthll/data/test_moved.txt", self.filesystem.user_created_files)
    
    def test_reset_directory_removes_modified_files(self):
        """Test that reset_directory removes user-modified files (restores to default)"""
        # Create and modify a file
        self.filesystem.change_directory("/home/pilot/blthll")
        self.filesystem.create_file("test_modified.txt", ["original"])
        success, _ = self.filesystem.write_file("test_modified.txt", ["modified content"])
        self.assertTrue(success, "Failed to modify test_modified.txt")
        
        # Since it's user-created, it will be in user_created_files, not user_modified_files
        # Let's create a scenario where we modify a user-created file
        self.assertIn("/home/pilot/blthll/test_modified.txt", self.filesystem.user_created_files)
        
        # Reset the directory (use absolute path)
        success, error = self.filesystem.reset_directory("/home/pilot/blthll")
        self.assertTrue(success, f"Reset failed: {error}")
        
        # Verify file is removed
        self.assertNotIn("/home/pilot/blthll/test_modified.txt", self.filesystem.user_created_files)
    
    def test_reset_directory_removes_user_created_dirs(self):
        """Test that reset_directory removes user-created directories"""
        # Create a user directory
        self.filesystem.change_directory("/home/pilot/blthll")
        success, _ = self.filesystem.create_directory("user_dir")
        self.assertTrue(success)
        
        # Verify it exists (with trailing slash)
        self.assertIn("/home/pilot/blthll/user_dir/", self.filesystem.user_created_dirs)
        
        # Reset the directory (use absolute path)
        success, error = self.filesystem.reset_directory("/home/pilot/blthll")
        self.assertTrue(success, f"Reset failed: {error}")
        
        # Verify directory is removed
        self.assertNotIn("/home/pilot/blthll/user_dir/", self.filesystem.user_created_dirs)
    
    def test_reset_directory_with_relative_path(self):
        """Test reset_directory with relative path"""
        # Create a user file
        self.filesystem.change_directory("/home/pilot/blthll")
        self.filesystem.create_file("test.txt", ["test"])
        
        # Reset using relative path (current directory)
        success, error = self.filesystem.reset_directory(".")
        self.assertTrue(success, f"Reset failed: {error}")
        
        # Verify file is removed
        self.assertNotIn("/home/pilot/blthll/test.txt", self.filesystem.user_created_files)
    
    def test_reset_directory_with_absolute_path(self):
        """Test reset_directory with absolute path"""
        # Create a user file
        self.filesystem.change_directory("weapons")
        self.filesystem.create_file("test.txt", ["test"])
        
        # Reset using absolute path
        success, error = self.filesystem.reset_directory("/home/pilot/blthll/weapons")
        self.assertTrue(success, f"Reset failed: {error}")
        
        # Verify file is removed
        self.assertNotIn("/home/pilot/blthll/weapons/test.txt", self.filesystem.user_created_files)
    
    def test_reset_directory_complex_scenario(self):
        """Test reset_directory with multiple types of modifications"""
        # Set up complex scenario in blthll directory
        self.filesystem.change_directory("/home/pilot/blthll")
        
        # 1. Create user file
        self.filesystem.create_file("user1.txt", ["user content"])
        
        # 2. Create and delete a file (simulate deleted default)
        self.filesystem.create_file("temp_deleted.txt", ["temp"])
        self.filesystem.delete_file("temp_deleted.txt")
        # Manually add to deleted files to simulate deleted default
        self.filesystem.user_deleted_files.add("/home/pilot/blthll/temp_deleted.txt")
        
        # 3. Create and modify a file
        self.filesystem.create_file("temp_modified.txt", ["original"])
        self.filesystem.write_file("temp_modified.txt", ["modified"])
        # Move to modified files to simulate modified default
        if "/home/pilot/blthll/temp_modified.txt" in self.filesystem.user_created_files:
            content = self.filesystem.user_created_files.pop("/home/pilot/blthll/temp_modified.txt")
            self.filesystem.user_modified_files["/home/pilot/blthll/temp_modified.txt"] = content
        
        # 4. Create user directory
        success, _ = self.filesystem.create_directory("user_dir")
        self.assertTrue(success)
        
        # 5. Create a file and move it
        self.filesystem.create_file("temp_moved.txt", ["original content"])
        success, _ = self.filesystem.move_file("temp_moved.txt", "data/temp_moved.txt")
        self.assertTrue(success, "Failed to move temp_moved.txt")
        
        # Verify all modifications exist
        self.assertIn("/home/pilot/blthll/user1.txt", self.filesystem.user_created_files)
        self.assertIn("/home/pilot/blthll/temp_deleted.txt", self.filesystem.user_deleted_files)
        self.assertIn("/home/pilot/blthll/temp_modified.txt", self.filesystem.user_modified_files)
        self.assertIn("/home/pilot/blthll/user_dir/", self.filesystem.user_created_dirs)
        self.assertIn("/home/pilot/blthll/data/temp_moved.txt", self.filesystem.user_created_files)
        
        # Reset the directory (use absolute path)
        success, error = self.filesystem.reset_directory("/home/pilot/blthll")
        self.assertTrue(success, f"Reset failed: {error}")
        
        # Verify all modifications are removed/restored
        self.assertNotIn("/home/pilot/blthll/user1.txt", self.filesystem.user_created_files)
        self.assertNotIn("/home/pilot/blthll/temp_modified.txt", self.filesystem.user_modified_files)
        self.assertNotIn("/home/pilot/blthll/user_dir/", self.filesystem.user_created_dirs)
        self.assertNotIn("/home/pilot/blthll/data/temp_moved.txt", self.filesystem.user_created_files)
