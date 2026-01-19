"""
Unit tests for filesystem permission handling
"""

import unittest
from src.unix.filesystem import VirtualFileSystem


class TestFilesystemPermissions(unittest.TestCase):
    """Test cases for filesystem permission operations"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.filesystem = VirtualFileSystem()
    
    def test_default_file_without_permissions(self):
        """Test that default files without explicit permissions default to rwxrwxrwx"""
        self.filesystem.change_directory('/home/pilot/blthll')
        perms = self.filesystem.get_permissions('readme.txt')
        self.assertEqual(perms, 'rwxrwxrwx', 
                        "Default file without permissions should be rwxrwxrwx")
    
    def test_default_file_with_permissions(self):
        """Test that default files with explicit permissions use those permissions"""
        self.filesystem.change_directory('data')
        perms = self.filesystem.get_permissions('highscores.txt')
        self.assertEqual(perms, 'r--------',
                        "Default file with r-------- permissions should preserve them")
    
    def test_user_created_file_default_permissions(self):
        """Test that user-created files default to rwxrwxrwx"""
        self.filesystem.change_directory('/home/pilot/blthll')
        self.filesystem.create_file('test_user.txt', ['test content'])
        perms = self.filesystem.get_permissions('test_user.txt')
        self.assertEqual(perms, 'rwxrwxrwx',
                        "User-created files should default to rwxrwxrwx")
    
    def test_move_preserves_non_default_permissions(self):
        """Test that moving a file with non-default permissions preserves them"""
        # Move a file with special permissions
        self.filesystem.change_directory('data')
        original_perms = self.filesystem.get_permissions('highscores.txt')
        self.assertEqual(original_perms, 'r--------',
                        "Source file should have r-------- permissions")
        
        # Need write permission to move
        self.filesystem.set_permissions('highscores.txt', 'rwxrwxrwx')
        success, _ = self.filesystem.move_file('highscores.txt', '../highscores_moved.txt')
        self.assertTrue(success, "Move should succeed")
        
        # Check permissions at destination
        self.filesystem.change_directory('/home/pilot/blthll')
        dest_perms = self.filesystem.get_permissions('highscores_moved.txt')
        self.assertEqual(dest_perms, 'r--------',
                        "Moved file should preserve original r-------- permissions")
        
        # Verify permissions are stored in file_permissions
        self.assertIn('/home/pilot/blthll/highscores_moved.txt', 
                     self.filesystem.file_permissions,
                     "Non-default permissions should be stored in file_permissions")
        self.assertEqual(self.filesystem.file_permissions['/home/pilot/blthll/highscores_moved.txt'],
                        'r--------',
                        "Stored permissions should match")
    
    def test_move_default_permissions_not_stored(self):
        """Test that moving a file with default permissions doesn't store them unnecessarily"""
        self.filesystem.change_directory('/home/pilot/blthll')
        # Move a file with default permissions
        self.filesystem.set_permissions('readme.txt', 'rwxrwxrwx')  # Need write to move
        success, _ = self.filesystem.move_file('readme.txt', 'data/readme_moved.txt')
        self.assertTrue(success, "Move should succeed")
        
        # Default permissions shouldn't be stored (they're the default)
        self.filesystem.change_directory('data')
        perms = self.filesystem.get_permissions('readme_moved.txt')
        self.assertEqual(perms, 'rwxrwxrwx',
                        "Moved file should have default permissions")
        
        # Should not be in file_permissions (since it's the default)
        self.assertNotIn('/home/pilot/blthll/data/readme_moved.txt',
                        self.filesystem.file_permissions,
                        "Default permissions should not be stored in file_permissions")
    
    def test_directory_default_permissions(self):
        """Test that directories default to rwxrwxrwx"""
        self.filesystem.change_directory('/home/pilot/blthll')
        # Test default directory
        perms = self.filesystem.get_permissions('data/')
        self.assertEqual(perms, 'rwxrwxrwx',
                        "Default directories should have rwxrwxrwx permissions")
        
        # Test with and without trailing slash
        perms_no_slash = self.filesystem.get_permissions('data')
        self.assertEqual(perms_no_slash, 'rwxrwxrwx',
                        "Directory permissions should work with or without trailing slash")
    
    def test_user_created_directory_default_permissions(self):
        """Test that user-created directories default to rwxrwxrwx"""
        self.filesystem.change_directory('/home/pilot/blthll')
        success, _ = self.filesystem.create_directory('test_dir')
        self.assertTrue(success, "Directory creation should succeed")
        
        perms = self.filesystem.get_permissions('test_dir/')
        self.assertEqual(perms, 'rwxrwxrwx',
                        "User-created directories should default to rwxrwxrwx")
    
    def test_directory_chmod(self):
        """Test that chmod works on directories"""
        self.filesystem.change_directory('/home/pilot/blthll')
        success, _ = self.filesystem.create_directory('test_chmod_dir')
        self.assertTrue(success, "Directory creation should succeed")
        
        # Set permissions
        success, error = self.filesystem.set_permissions('test_chmod_dir/', 'r-xr-xr-x')
        self.assertTrue(success, f"chmod should succeed: {error}")
        
        # Verify permissions
        perms = self.filesystem.get_permissions('test_chmod_dir/')
        self.assertEqual(perms, 'r-xr-xr-x',
                        "Directory permissions should be updated by chmod")
        
        # Verify stored in file_permissions
        self.assertIn('/home/pilot/blthll/test_chmod_dir',
                     self.filesystem.file_permissions,
                     "Directory permissions should be stored in file_permissions")
    
    def test_directory_chmod_without_trailing_slash(self):
        """Test that chmod works on directories without trailing slash"""
        self.filesystem.change_directory('/home/pilot/blthll')
        success, _ = self.filesystem.create_directory('test_chmod_dir2')
        self.assertTrue(success, "Directory creation should succeed")
        
        # Set permissions without trailing slash
        success, error = self.filesystem.set_permissions('test_chmod_dir2', 'r-xr-xr-x')
        self.assertTrue(success, f"chmod should succeed: {error}")
        
        # Verify permissions work with both formats
        perms_with_slash = self.filesystem.get_permissions('test_chmod_dir2/')
        perms_without_slash = self.filesystem.get_permissions('test_chmod_dir2')
        self.assertEqual(perms_with_slash, 'r-xr-xr-x',
                        "Directory permissions should work with trailing slash")
        self.assertEqual(perms_without_slash, 'r-xr-xr-x',
                        "Directory permissions should work without trailing slash")
    
    def test_file_chmod_preserves_permissions(self):
        """Test that chmod on files works and preserves permissions"""
        self.filesystem.change_directory('/home/pilot/blthll')
        self.filesystem.create_file('test_chmod.txt', ['test'])
        
        # Set permissions
        success, error = self.filesystem.set_permissions('test_chmod.txt', 'r--r--r--')
        self.assertTrue(success, f"chmod should succeed: {error}")
        
        # Verify permissions
        perms = self.filesystem.get_permissions('test_chmod.txt')
        self.assertEqual(perms, 'r--r--r--',
                        "File permissions should be updated by chmod")
        
        # Verify stored
        self.assertIn('/home/pilot/blthll/test_chmod.txt',
                     self.filesystem.file_permissions,
                     "File permissions should be stored in file_permissions")
    
    def test_permissions_3_char_expansion(self):
        """Test that 3-character permissions are expanded to 9-character"""
        self.filesystem.change_directory('/home/pilot/blthll')
        self.filesystem.create_file('test_3char.txt', ['test'])
        
        # Set 3-character permissions
        success, error = self.filesystem.set_permissions('test_3char.txt', 'rw-')
        self.assertTrue(success, f"chmod should succeed: {error}")
        
        # Verify they're expanded to 9-character
        perms = self.filesystem.get_permissions('test_3char.txt')
        self.assertEqual(len(perms), 9,
                        "3-character permissions should be expanded to 9-character")
        self.assertEqual(perms, 'rw-rw-rw-',
                        "3-character permissions should be repeated for user, group, other")
    
    def test_permissions_octal_format(self):
        """Test that octal permission formats work"""
        self.filesystem.change_directory('/home/pilot/blthll')
        self.filesystem.create_file('test_octal.txt', ['test'])
        
        # Test octal format
        success, error = self.filesystem.set_permissions('test_octal.txt', '644')
        self.assertTrue(success, f"chmod should succeed: {error}")
        
        perms = self.filesystem.get_permissions('test_octal.txt')
        self.assertEqual(perms, 'rw-r--r--',
                        "Octal 644 should convert to rw-r--r--")
        
        # Test 4-digit octal
        success, error = self.filesystem.set_permissions('test_octal.txt', '0755')
        self.assertTrue(success, f"chmod should succeed: {error}")
        
        perms = self.filesystem.get_permissions('test_octal.txt')
        self.assertEqual(perms, 'rwxr-xr-x',
                        "Octal 0755 should convert to rwxr-xr-x")
    
    def test_permissions_after_reset_directory(self):
        """Test that permissions are preserved after reset_directory"""
        self.filesystem.change_directory('data')
        
        # Create a file with custom permissions
        self.filesystem.create_file('test_reset.txt', ['test'])
        self.filesystem.set_permissions('test_reset.txt', 'r--r--r--')
        
        # Reset the directory
        success, error = self.filesystem.reset_directory('/home/pilot/blthll/data')
        self.assertTrue(success, f"Reset should succeed: {error}")
        
        # File should be removed, so permissions should be gone
        self.assertNotIn('/home/pilot/blthll/data/test_reset.txt',
                        self.filesystem.file_permissions,
                        "Permissions should be removed when file is removed")
    
    def test_permissions_after_reset_filesystem(self):
        """Test that permissions are reset after reset_filesystem"""
        self.filesystem.change_directory('/home/pilot/blthll')
        
        # Create files with custom permissions
        self.filesystem.create_file('test1.txt', ['test1'])
        self.filesystem.create_file('test2.txt', ['test2'])
        self.filesystem.set_permissions('test1.txt', 'r--r--r--')
        self.filesystem.set_permissions('test2.txt', 'rw-rw-rw-')
        
        # Reset filesystem
        self.filesystem.reset_to_defaults()
        
        # All permissions should be cleared
        self.assertEqual(len(self.filesystem.file_permissions), 0,
                        "All permissions should be cleared after reset")
    
    def test_permissions_save_and_load(self):
        """Test that permissions are saved and loaded correctly"""
        self.filesystem.change_directory('/home/pilot/blthll')
        
        # Create files with custom permissions
        self.filesystem.create_file('test_save1.txt', ['test1'])
        self.filesystem.create_file('test_save2.txt', ['test2'])
        self.filesystem.set_permissions('test_save1.txt', 'r--r--r--')
        self.filesystem.set_permissions('test_save2.txt', 'rw-rw-rw-')
        
        # Save state
        state = self.filesystem.get_state()
        
        # Create new filesystem and restore
        new_fs = VirtualFileSystem(saved_state=state)
        
        # Verify permissions are restored
        new_fs.change_directory('/home/pilot/blthll')
        self.assertIn('/home/pilot/blthll/test_save1.txt', new_fs.file_permissions)
        self.assertIn('/home/pilot/blthll/test_save2.txt', new_fs.file_permissions)
        self.assertEqual(new_fs.file_permissions['/home/pilot/blthll/test_save1.txt'],
                        'r--r--r--',
                        "Permissions should be restored correctly")
        self.assertEqual(new_fs.file_permissions['/home/pilot/blthll/test_save2.txt'],
                        'rw-rw-rw-',
                        "Permissions should be restored correctly")
