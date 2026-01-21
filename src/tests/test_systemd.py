"""
Unit tests for systemd and systemctl functionality
"""

import unittest
from src.unix.filesystem import VirtualFileSystem
from src.unix.systemd_manager import SystemdManager


class FakeSaveSystem:
    """Minimal save system for testing systemd persistence"""
    
    def __init__(self):
        self.data = {
            "systemd_states": None,
            "systemd_enabled": None
        }
    
    def get_systemd_states(self):
        return self.data.get("systemd_states")
    
    def save_systemd_states(self, states):
        self.data["systemd_states"] = states
    
    def get_systemd_enabled(self):
        return self.data.get("systemd_enabled")
    
    def save_systemd_enabled(self, enabled):
        self.data["systemd_enabled"] = enabled


class TestSystemdDirectories(unittest.TestCase):
    """Test that systemd directories exist and have correct structure"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.filesystem = VirtualFileSystem()
    
    def test_systemd_directories_exist(self):
        """Test that all required systemd directories exist"""
        # Check /usr/lib/systemd/system/
        self.filesystem.change_directory('/usr/lib/systemd/system')
        self.assertEqual(self.filesystem.get_pwd(), '/usr/lib/systemd/system')
        
        # Check /run/systemd/system/
        self.filesystem.change_directory('/run/systemd/system')
        self.assertEqual(self.filesystem.get_pwd(), '/run/systemd/system')
        
        # Check /etc/systemd/system/
        self.filesystem.change_directory('/etc/systemd/system')
        self.assertEqual(self.filesystem.get_pwd(), '/etc/systemd/system')
    
    def test_systemd_directories_owned_by_root(self):
        """Test that systemd directories are owned by root"""
        self.filesystem.change_directory('/usr/lib/systemd/system')
        owner = self.filesystem.get_file_owner('.')
        self.assertEqual(owner, 'root', "Systemd directories should be owned by root")
        
        self.filesystem.change_directory('/run/systemd/system')
        owner = self.filesystem.get_file_owner('.')
        self.assertEqual(owner, 'root', "Runtime systemd directory should be owned by root")
        
        self.filesystem.change_directory('/etc/systemd/system')
        owner = self.filesystem.get_file_owner('.')
        self.assertEqual(owner, 'root', "Enabled systemd directory should be owned by root")


class TestSystemdUnitFiles(unittest.TestCase):
    """Test systemd unit files exist and have correct properties"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.filesystem = VirtualFileSystem()
    
    def test_default_unit_files_exist(self):
        """Test that default unit files exist in /usr/lib/systemd/system/"""
        self.filesystem.change_directory('/usr/lib/systemd/system')
        
        # Check that unit files exist
        self.assertTrue(self.filesystem.file_exists('blthll.service'),
                       "blthll.service should exist")
        self.assertTrue(self.filesystem.file_exists('network.service'),
                       "network.service should exist")
        self.assertTrue(self.filesystem.file_exists('sshd.service'),
                       "sshd.service should exist")
    
    def test_unit_files_owned_by_root(self):
        """Test that unit files are owned by root"""
        self.filesystem.change_directory('/usr/lib/systemd/system')
        
        owner = self.filesystem.get_file_owner('blthll.service')
        self.assertEqual(owner, 'root', "Unit files should be owned by root")
        
        owner = self.filesystem.get_file_owner('network.service')
        self.assertEqual(owner, 'root', "Unit files should be owned by root")
        
        owner = self.filesystem.get_file_owner('sshd.service')
        self.assertEqual(owner, 'root', "Unit files should be owned by root")
    
    def test_unit_files_permissions(self):
        """Test that unit files have correct permissions (rw-r--r--)"""
        self.filesystem.change_directory('/usr/lib/systemd/system')
        
        perms = self.filesystem.get_permissions('blthll.service')
        self.assertEqual(perms, 'rw-r--r--',
                       "Unit files should have rw-r--r-- permissions")
        
        perms = self.filesystem.get_permissions('network.service')
        self.assertEqual(perms, 'rw-r--r--',
                       "Unit files should have rw-r--r-- permissions")
    
    def test_unit_files_readable_by_pilot(self):
        """Test that pilot can read unit files"""
        self.filesystem.change_directory('/usr/lib/systemd/system')
        
        # Pilot should be able to read
        self.assertTrue(self.filesystem.check_permission('blthll.service', 'r'),
                       "Pilot should be able to read unit files")
        
        # Read the file to verify
        success, content = self.filesystem.read_file('blthll.service')
        self.assertTrue(success, "Pilot should be able to read unit file")
        self.assertIn('[Unit]', content, "Unit file should contain [Unit] section")
    
    def test_unit_files_not_writable_by_pilot(self):
        """Test that pilot cannot write to unit files"""
        self.filesystem.change_directory('/usr/lib/systemd/system')
        
        # Pilot should NOT be able to write
        self.assertFalse(self.filesystem.check_permission('blthll.service', 'w'),
                        "Pilot should NOT be able to write to unit files")
        
        # Try to write (should fail)
        success, error = self.filesystem.write_file('blthll.service', 'test')
        self.assertFalse(success, "Pilot should not be able to write to unit file")
        self.assertIn('Permission denied', error)
    
    def test_unit_files_writable_by_root(self):
        """Test that root can write to unit files"""
        self.filesystem.change_directory('/usr/lib/systemd/system')
        self.filesystem.set_user('root')
        
        # Root should be able to write
        self.assertTrue(self.filesystem.check_permission('blthll.service', 'w'),
                       "Root should be able to write to unit files")
        
        # Write to the file
        success, error = self.filesystem.write_file('blthll.service', 'test content')
        self.assertTrue(success, f"Root should be able to write to unit file: {error}")


class TestSystemdManager(unittest.TestCase):
    """Test SystemdManager functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.filesystem = VirtualFileSystem()
        self.save_system = FakeSaveSystem()
        self.manager = SystemdManager(self.filesystem, self.save_system)
    
    def test_default_service_states(self):
        """Test that default services have correct initial states"""
        state = self.manager.get_service_state('blthll.service')
        self.assertEqual(state, 'active', "blthll.service should be active by default")
        
        state = self.manager.get_service_state('network.service')
        self.assertEqual(state, 'active', "network.service should be active by default")
        
        state = self.manager.get_service_state('sshd.service')
        self.assertEqual(state, 'inactive', "sshd.service should be inactive by default")
    
    def test_default_enabled_services(self):
        """Test that default services are correctly enabled"""
        self.assertTrue(self.manager.is_enabled('blthll.service'),
                       "blthll.service should be enabled by default")
        self.assertTrue(self.manager.is_enabled('network.service'),
                       "network.service should be enabled by default")
        self.assertFalse(self.manager.is_enabled('sshd.service'),
                        "sshd.service should not be enabled by default")
    
    def test_start_service(self):
        """Test starting a service"""
        # Start an inactive service
        success, message = self.manager.start_service('sshd.service')
        self.assertTrue(success, f"Should be able to start service: {message}")
        self.assertIn('started successfully', message)
        
        # Check state
        state = self.manager.get_service_state('sshd.service')
        self.assertEqual(state, 'active', "Service should be active after start")
        
        # Try to start an already active service
        success, message = self.manager.start_service('blthll.service')
        self.assertTrue(success, "Should handle already active service")
        self.assertIn('already active', message)
    
    def test_stop_service(self):
        """Test stopping a service"""
        # Stop an active service
        success, message = self.manager.stop_service('blthll.service')
        self.assertTrue(success, f"Should be able to stop service: {message}")
        self.assertIn('stopped successfully', message)
        
        # Check state
        state = self.manager.get_service_state('blthll.service')
        self.assertEqual(state, 'inactive', "Service should be inactive after stop")
        
        # Try to stop an already inactive service
        success, message = self.manager.stop_service('sshd.service')
        self.assertTrue(success, "Should handle already inactive service")
        self.assertIn('already inactive', message)
    
    def test_enable_service(self):
        """Test enabling a service"""
        # Enable sshd (not enabled by default)
        success, message = self.manager.enable_service('sshd.service')
        self.assertTrue(success, f"Should be able to enable service: {message}")
        self.assertIn('enabled successfully', message)
        
        # Check that it's enabled
        self.assertTrue(self.manager.is_enabled('sshd.service'),
                      "Service should be enabled after enable")
        
        # Check that symlink was created in /etc/systemd/system/
        self.filesystem.change_directory('/etc/systemd/system')
        self.assertTrue(self.filesystem.file_exists('sshd.service'),
                       "Symlink should exist in /etc/systemd/system/")
    
    def test_disable_service(self):
        """Test disabling a service"""
        # Disable blthll (enabled by default)
        success, message = self.manager.disable_service('blthll.service')
        self.assertTrue(success, f"Should be able to disable service: {message}")
        self.assertIn('disabled successfully', message)
        
        # Check that it's disabled
        self.assertFalse(self.manager.is_enabled('blthll.service'),
                        "Service should be disabled after disable")
        
        # Check that symlink was removed from /etc/systemd/system/
        self.filesystem.change_directory('/etc/systemd/system')
        self.assertFalse(self.filesystem.file_exists('blthll.service'),
                        "Symlink should be removed from /etc/systemd/system/")
    
    def test_enable_nonexistent_service(self):
        """Test that enabling a non-existent service fails"""
        success, message = self.manager.enable_service('nonexistent.service')
        self.assertFalse(success, "Should not be able to enable non-existent service")
        self.assertIn('not found', message)
    
    def test_list_unit_files(self):
        """Test listing unit files"""
        unit_files = self.manager.list_unit_files()
        
        # Should find default unit files
        service_names = [f[0] for f in unit_files]
        self.assertIn('blthll.service', service_names,
                     "Should list blthll.service")
        self.assertIn('network.service', service_names,
                     "Should list network.service")
        self.assertIn('sshd.service', service_names,
                     "Should list sshd.service")
        
        # Check locations
        for name, location, enabled in unit_files:
            if name == 'blthll.service':
                self.assertEqual(location, '/usr/lib/systemd/system/',
                               "Default unit files should be in /usr/lib/systemd/system/")
    
    def test_list_units(self):
        """Test listing all units"""
        units = self.manager.list_units()
        
        # Should list all services
        service_names = [u[0] for u in units]
        self.assertIn('blthll.service', service_names)
        self.assertIn('network.service', service_names)
        self.assertIn('sshd.service', service_names)
        
        # Check states
        for name, state, enabled in units:
            if name == 'blthll.service':
                self.assertEqual(state, 'active')
                self.assertTrue(enabled)
            elif name == 'sshd.service':
                self.assertEqual(state, 'inactive')
                self.assertFalse(enabled)


class TestSystemdOwnershipPreservation(unittest.TestCase):
    """Test that ownership is preserved when moving systemd files"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.filesystem = VirtualFileSystem()
    
    def test_move_root_owned_unit_file_preserves_ownership(self):
        """Test that moving a root-owned unit file preserves ownership"""
        self.filesystem.change_directory('/usr/lib/systemd/system')
        
        # Verify original ownership
        original_owner = self.filesystem.get_file_owner('blthll.service')
        self.assertEqual(original_owner, 'root', "Original file should be owned by root")
        
        # Move as root (need root to move root-owned file)
        self.filesystem.set_user('root')
        success, error = self.filesystem.move_file('blthll.service', '/home/pilot/blthll/blthll.service')
        self.assertTrue(success, f"Should be able to move file as root: {error}")
        
        # Check ownership at destination
        self.filesystem.change_directory('/home/pilot/blthll')
        new_owner = self.filesystem.get_file_owner('blthll.service')
        self.assertEqual(new_owner, 'root',
                        "Moved file should preserve root ownership")
        
        # Verify it's in file_owners
        self.assertIn('/home/pilot/blthll/blthll.service', self.filesystem.file_owners,
                     "Ownership should be tracked in file_owners")
        self.assertEqual(self.filesystem.file_owners['/home/pilot/blthll/blthll.service'],
                        'root', "Stored ownership should be root")
    
    def test_move_root_owned_unit_file_preserves_permissions(self):
        """Test that moving a root-owned unit file preserves permissions"""
        self.filesystem.change_directory('/usr/lib/systemd/system')
        
        # Verify original permissions
        original_perms = self.filesystem.get_permissions('blthll.service')
        self.assertEqual(original_perms, 'rw-r--r--',
                        "Original file should have rw-r--r-- permissions")
        
        # Move as root
        self.filesystem.set_user('root')
        success, error = self.filesystem.move_file('blthll.service', '/home/pilot/blthll/blthll.service')
        self.assertTrue(success, f"Should be able to move file: {error}")
        
        # Check permissions at destination
        self.filesystem.change_directory('/home/pilot/blthll')
        new_perms = self.filesystem.get_permissions('blthll.service')
        self.assertEqual(new_perms, 'rw-r--r--',
                        "Moved file should preserve permissions")
    
    def test_pilot_cannot_move_root_owned_unit_file(self):
        """Test that pilot cannot move root-owned unit files"""
        self.filesystem.change_directory('/usr/lib/systemd/system')
        
        # Try to move as pilot (should fail)
        success, error = self.filesystem.move_file('blthll.service', '/home/pilot/blthll/blthll.service')
        self.assertFalse(success, "Pilot should not be able to move root-owned file")
        self.assertIn('Permission denied', error)
        
        # Verify file is still in original location
        self.assertTrue(self.filesystem.file_exists('blthll.service'),
                       "File should still be in original location")


class TestSystemdPersistence(unittest.TestCase):
    """Test that systemd state persists across sessions"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.filesystem = VirtualFileSystem()
        self.save_system = FakeSaveSystem()
    
    def test_service_state_persistence(self):
        """Test that service states are saved and restored"""
        # Create manager and change a state
        manager1 = SystemdManager(self.filesystem, self.save_system)
        manager1.set_service_state('sshd.service', 'active')
        
        # Create new manager (simulating restart)
        manager2 = SystemdManager(self.filesystem, self.save_system)
        
        # Check that state was restored
        state = manager2.get_service_state('sshd.service')
        self.assertEqual(state, 'active',
                        "Service state should be restored from save")
    
    def test_enabled_services_persistence(self):
        """Test that enabled services are saved and restored"""
        # Create manager and enable a service
        manager1 = SystemdManager(self.filesystem, self.save_system)
        manager1.enable_service('sshd.service')
        
        # Create new manager (simulating restart)
        manager2 = SystemdManager(self.filesystem, self.save_system)
        
        # Check that enabled state was restored
        self.assertTrue(manager2.is_enabled('sshd.service'),
                       "Enabled state should be restored from save")


if __name__ == '__main__':
    unittest.main()
