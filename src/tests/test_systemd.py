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
            "systemd_enabled": None,
            "unlocked_games": []
        }

    def get_systemd_states(self):
        return self.data.get("systemd_states")

    def save_systemd_states(self, states):
        self.data["systemd_states"] = states

    def get_systemd_enabled(self):
        return self.data.get("systemd_enabled")

    def save_systemd_enabled(self, enabled):
        self.data["systemd_enabled"] = enabled

    def is_game_unlocked(self, game_key):
        """Check if a game is unlocked"""
        return game_key in self.data.get("unlocked_games", [])

    def unlock_game(self, game_key):
        """Unlock a game"""
        if game_key not in self.data["unlocked_games"]:
            self.data["unlocked_games"].append(game_key)


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
        # Start sshd first (it's inactive by default)
        self.manager.start_service('sshd.service')

        # Stop a non-critical service (sshd is not critical)
        success, message = self.manager.stop_service('sshd.service')
        self.assertTrue(success, f"Should be able to stop non-critical service: {message}")
        self.assertIn('stopped successfully', message)

        # Check state
        state = self.manager.get_service_state('sshd.service')
        self.assertEqual(state, 'inactive', "Service should be inactive after stop")

        # Try to stop an already inactive service
        success, message = self.manager.stop_service('sshd.service')
        self.assertTrue(success, "Should handle already inactive service")
        self.assertIn('already inactive', message)

    def test_stop_critical_service_triggers_reset(self):
        """Test that stopping a critical service triggers system reset"""
        # Try to stop a critical service
        success, message = self.manager.stop_service('blthll.service')
        self.assertFalse(success, "Stopping critical service should fail and trigger reset")
        self.assertIn('CRITICAL', message)
        self.assertIn('SYSTEM FAILURE', message)

        # Check that reset was triggered
        self.assertTrue(self.manager.was_system_reset_triggered(),
                       "System reset should be triggered")

        # Check that critical service was restored
        state = self.manager.get_service_state('blthll.service')
        self.assertEqual(state, 'active', "Critical service should be restored to active")

        # Clear reset flag for other tests
        self.manager.clear_reset_flag()

    def test_cascading_failure_triggers_reset(self):
        """Test that stopping a critical service via conflict triggers reset"""
        # Create a service that conflicts with network.service (critical)
        # First, create a unit file that conflicts with network
        self.filesystem.change_directory('/usr/lib/systemd/system')
        self.filesystem.create_file('test-conflict.service', [
            "[Unit]",
            "Description=Test Conflict Service",
            "Conflicts=network.service",
            "",
            "[Service]",
            "Type=oneshot",
            "ExecStart=/bin/true"
        ])

        # Try to start the conflicting service
        # This should stop network.service (critical) and trigger reset
        success, message = self.manager.start_service('test-conflict.service')
        self.assertFalse(success, "Starting service that conflicts with critical service should trigger reset")
        self.assertIn('CRITICAL', message)

        # Check that reset was triggered
        self.assertTrue(self.manager.was_system_reset_triggered(),
                       "System reset should be triggered")

        # Check that critical service was restored
        state = self.manager.get_service_state('network.service')
        self.assertEqual(state, 'active', "Critical service should be restored to active")

        # Clean up
        self.manager.clear_reset_flag()
        self.filesystem.delete_file('test-conflict.service')

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
        for name, location, _enabled in unit_files:
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


class TestDependencyPuzzle(unittest.TestCase):
    """Test the complete dependency puzzle solution flow"""

    def setUp(self):
        """Set up test fixtures"""
        self.filesystem = VirtualFileSystem()
        self.save_system = FakeSaveSystem()
        self.manager = SystemdManager(self.filesystem, self.save_system)

    def test_stage1_systemctl_not_available_initially(self):
        """Stage 1: Verify systemctl is not available initially"""
        # Check that /bin/systemctl doesn't exist
        self.filesystem.change_directory('/bin')
        self.assertFalse(self.filesystem.file_exists('systemctl'),
                        "systemctl should not exist in /bin initially")

        # Check that broken systemctl exists in deprecated location
        self.filesystem.change_directory('/usr/local/deprecated')
        self.assertTrue(self.filesystem.file_exists('sys_control.py'),
                       "Broken systemctl should exist in /usr/local/deprecated/")

    def test_stage1_boot_log_exists(self):
        """Stage 1: Verify boot.log exists with error messages"""
        self.filesystem.change_directory('/var/log')
        self.assertTrue(self.filesystem.file_exists('boot.log'),
                       "boot.log should exist")

        success, content = self.filesystem.read_file('boot.log')
        self.assertTrue(success, "Should be able to read boot.log")
        content_str = '\n'.join(content) if isinstance(content, list) else str(content)
        self.assertIn('laser.service', content_str,
                     "boot.log should mention laser.service")
        self.assertIn('systemctl status', content_str,
                     "boot.log should mention systemctl status")

    def test_stage1_fix_systemctl(self):
        """Stage 1: Fix systemctl by moving and making executable"""
        # Read the broken systemctl
        self.filesystem.change_directory('/usr/local/deprecated')
        success, content = self.filesystem.read_file('sys_control.py')
        self.assertTrue(success, "Should be able to read broken systemctl")

        # Move to /bin/systemctl
        self.filesystem.set_user('root')  # Need root to move to /bin
        success, error = self.filesystem.move_file('sys_control.py', '/bin/systemctl')
        self.assertTrue(success, f"Should be able to move systemctl: {error}")

        # Make it executable
        self.filesystem.change_directory('/bin')
        success, error = self.filesystem.set_permissions('systemctl', '755')
        self.assertTrue(success, f"Should be able to make systemctl executable: {error}")

        # Verify it's now available
        perms = self.filesystem.get_permissions('systemctl')
        self.assertIn('x', perms[:3], "systemctl should be executable")

    def test_stage2_shield_service_masked(self):
        """Stage 2: Verify shield.service cannot be stopped (masked)"""
        success, message = self.manager.stop_service('shield.service')
        self.assertFalse(success, "shield.service should not be stoppable")
        self.assertIn('masked', message.lower(),
                     "Error should mention 'masked'")
        self.assertIn('System Integrity Protection', message,
                     "Error should mention System Integrity Protection")

    def test_stage2_status_shows_file_path(self):
        """Stage 2: Verify systemctl status shows unit file path"""
        # This would be tested through the main_menu integration, but we can verify
        # that the manager can resolve the path
        path = self.manager._resolve_unit_path('shield.service')
        self.assertIsNotNone(path, "Should be able to resolve shield.service path")
        self.assertIn('shield.service', path)
        self.assertIn('/usr/lib/systemd/system/', path)

    def test_stage3_admin_notes_exist(self):
        """Stage 3: Verify admin notes file exists with override instructions"""
        self.filesystem.change_directory('/home/pilot/blthll/data/secret')
        self.assertTrue(self.filesystem.file_exists('admin_notes.txt'),
                       "admin_notes.txt should exist")

        success, content = self.filesystem.read_file('admin_notes.txt')
        self.assertTrue(success, "Should be able to read admin_notes.txt")
        content_str = '\n'.join(content) if isinstance(content, list) else str(content)
        self.assertIn('.d', content_str,
                     "admin_notes.txt should mention .d directories")
        self.assertIn('override', content_str.lower(),
                     "admin_notes.txt should mention overrides")

    def test_stage4_create_override_directory(self):
        """Stage 4: Create override directory"""
        self.filesystem.set_user('root')  # Need root to create in /etc/systemd/system/
        self.filesystem.change_directory('/etc/systemd/system')

        success, error = self.filesystem.create_directory('cooler.service.d')
        self.assertTrue(success, f"Should be able to create override directory: {error}")

        # Verify directory exists by trying to cd into it
        old_pwd = self.filesystem.get_pwd()
        success, error = self.filesystem.change_directory('cooler.service.d')
        self.assertTrue(success, f"Should be able to cd into override directory: {error}")
        self.filesystem.change_directory(old_pwd)

    def test_stage4_create_override_file(self):
        """Stage 4: Create override file with Conflicts=laser.service"""
        self.filesystem.set_user('root')
        self.filesystem.change_directory('/etc/systemd/system')

        # Create directory first
        self.filesystem.create_directory('cooler.service.d')

        # Create override file
        self.filesystem.change_directory('cooler.service.d')
        override_content = [
            "[Unit]",
            "Conflicts=laser.service"
        ]
        success, error = self.filesystem.create_file('override.conf', override_content)
        self.assertTrue(success, f"Should be able to create override file: {error}")

        # Verify file exists and has correct content
        self.assertTrue(self.filesystem.file_exists('override.conf'),
                       "override.conf should exist")
        success, content = self.filesystem.read_file('override.conf')
        self.assertTrue(success)
        content_str = '\n'.join(content) if isinstance(content, list) else str(content)
        self.assertIn('Conflicts=laser.service', content_str,
                     "Override file should contain Conflicts=laser.service")

    def test_stage4_drop_in_override_parsing(self):
        """Stage 4: Verify drop-in overrides are parsed correctly"""
        # Set up override
        self.filesystem.set_user('root')
        self.filesystem.change_directory('/etc/systemd/system')
        self.filesystem.create_directory('cooler.service.d')
        self.filesystem.change_directory('cooler.service.d')
        override_content = [
            "[Unit]",
            "Conflicts=laser.service"
        ]
        success, error = self.filesystem.create_file('override.conf', override_content)
        self.assertTrue(success, f"Should be able to create override file: {error}")

        # Verify file exists before trying to get merged content
        self.assertTrue(self.filesystem.file_exists('override.conf'),
                       "override.conf should exist in current directory")

        # Reset to a known directory before calling manager
        self.filesystem.change_directory('/home/pilot/blthll')

        # Get merged content
        content = self.manager._get_unit_file_content('cooler.service')
        # The merged content should include the override
        self.assertIn('Conflicts=laser.service', content,
                     "Merged content should include override Conflicts")

        # Parse dependencies
        deps = self.manager._parse_dependencies(content)
        self.assertIn('laser.service', deps.get('Conflicts', []),
                     "Parsed dependencies should include laser.service in Conflicts")

    def test_stage4_laser_start_triggers_deadlock(self):
        """Stage 4: Verify starting laser.service triggers deadlock"""
        # Create override first (before starting cooler)
        self.filesystem.set_user('root')
        self.filesystem.change_directory('/etc/systemd/system')
        self.filesystem.create_directory('cooler.service.d')
        self.filesystem.change_directory('cooler.service.d')
        self.filesystem.create_file('override.conf', [
            "[Unit]",
            "Conflicts=laser.service"
        ])

        # Start cooler first (laser requires it)
        self.manager.set_service_state('cooler.service', 'active')

        # Try to start laser (requires cooler, but cooler conflicts with laser)
        # Laser will start cooler (requirement), but then cooler conflicts with laser
        # So cooler gets stopped, but laser requires cooler = deadlock
        success, message = self.manager.start_service('laser.service')
        self.assertFalse(success, "laser.service should fail to start")
        self.assertIn('OVERHEAT DETECTED', message,
                     "Error message should mention OVERHEAT DETECTED")
        self.assertIn('Boss Vulnerable', message,
                     "Error message should mention Boss Vulnerable")

    def test_puzzle_check_requires_systemctl_fixed(self):
        """Verify puzzle check requires systemctl to be fixed"""
        from src.core.puzzle_system import _check_dependency_puzzle

        # Without systemctl fixed, puzzle should not be solved
        result = _check_dependency_puzzle(self.filesystem)
        self.assertFalse(result, "Puzzle should not be solved without systemctl fixed")

    def test_puzzle_check_requires_override_directory(self):
        """Verify puzzle check requires override directory"""
        from src.core.puzzle_system import _check_dependency_puzzle

        # Fix systemctl first
        self.filesystem.set_user('root')
        self.filesystem.change_directory('/usr/local/deprecated')
        self.filesystem.move_file('sys_control.py', '/bin/systemctl')
        self.filesystem.change_directory('/bin')
        self.filesystem.set_permissions('systemctl', '755')

        # Without override directory, puzzle should not be solved
        result = _check_dependency_puzzle(self.filesystem)
        self.assertFalse(result, "Puzzle should not be solved without override directory")

    def test_puzzle_check_requires_override_file(self):
        """Verify puzzle check requires override file"""
        from src.core.puzzle_system import _check_dependency_puzzle

        # Fix systemctl
        self.filesystem.set_user('root')
        self.filesystem.change_directory('/usr/local/deprecated')
        self.filesystem.move_file('sys_control.py', '/bin/systemctl')
        self.filesystem.change_directory('/bin')
        self.filesystem.set_permissions('systemctl', '755')

        # Create override directory but no file
        self.filesystem.change_directory('/etc/systemd/system')
        self.filesystem.create_directory('cooler.service.d')

        # Without override file, puzzle should not be solved
        result = _check_dependency_puzzle(self.filesystem)
        self.assertFalse(result, "Puzzle should not be solved without override file")

    def test_puzzle_check_requires_correct_override_content(self):
        """Verify puzzle check requires Conflicts=laser.service in override"""
        from src.core.puzzle_system import _check_dependency_puzzle

        # Fix systemctl
        self.filesystem.set_user('root')
        self.filesystem.change_directory('/usr/local/deprecated')
        self.filesystem.move_file('sys_control.py', '/bin/systemctl')
        self.filesystem.change_directory('/bin')
        self.filesystem.set_permissions('systemctl', '755')

        # Create override directory and file with wrong content
        self.filesystem.change_directory('/etc/systemd/system')
        self.filesystem.create_directory('cooler.service.d')
        self.filesystem.change_directory('cooler.service.d')
        self.filesystem.create_file('override.conf', [
            "[Unit]",
            "Requires=laser.service"  # Wrong - should be Conflicts
        ])

        # With wrong content, puzzle should not be solved
        result = _check_dependency_puzzle(self.filesystem)
        self.assertFalse(result, "Puzzle should not be solved with wrong override content")

    def test_puzzle_check_succeeds_when_all_conditions_met(self):
        """Verify puzzle check succeeds when all conditions are met"""
        from src.core.puzzle_system import _check_dependency_puzzle

        # 1. Fix systemctl
        self.filesystem.set_user('root')
        self.filesystem.change_directory('/usr/local/deprecated')
        self.filesystem.move_file('sys_control.py', '/bin/systemctl')
        self.filesystem.change_directory('/bin')
        self.filesystem.set_permissions('systemctl', '755')

        # 2. Create override directory
        self.filesystem.change_directory('/etc/systemd/system')
        self.filesystem.create_directory('cooler.service.d')

        # 3. Create override file with Conflicts=laser.service
        self.filesystem.change_directory('cooler.service.d')
        self.filesystem.create_file('override.conf', [
            "[Unit]",
            "Conflicts=laser.service"
        ])

        # Puzzle should be solved
        result = _check_dependency_puzzle(self.filesystem)
        self.assertTrue(result, "Puzzle should be solved when all conditions are met")

    def test_puzzle_unlocks_oregon_trail(self):
        """Verify solving the puzzle unlocks oregon_trail game"""
        from src.core.puzzle_system import check_puzzles

        # Set up complete solution
        self.filesystem.set_user('root')
        self.filesystem.change_directory('/usr/local/deprecated')
        self.filesystem.move_file('sys_control.py', '/bin/systemctl')
        self.filesystem.change_directory('/bin')
        self.filesystem.set_permissions('systemctl', '755')

        self.filesystem.change_directory('/etc/systemd/system')
        self.filesystem.create_directory('cooler.service.d')
        self.filesystem.change_directory('cooler.service.d')
        self.filesystem.create_file('override.conf', [
            "[Unit]",
            "Conflicts=laser.service"
        ])

        # Check puzzle (triggered by systemctl command)
        newly_unlocked = check_puzzles(self.filesystem, self.save_system, "systemctl")

        # Should unlock oregon_trail
        self.assertEqual(len(newly_unlocked), 1, "Should unlock one game")
        game_key, message = newly_unlocked[0]
        self.assertEqual(game_key, "oregon_trail", "Should unlock oregon_trail")
        self.assertIn("oregon_trail", message.lower(), "Message should mention oregon_trail")

        # Verify game is unlocked in save system
        self.assertTrue(self.save_system.is_game_unlocked("oregon_trail"),
                       "Asteroids should be unlocked in save system")

    def test_puzzle_does_not_unlock_if_already_unlocked(self):
        """Verify puzzle doesn't unlock again if already unlocked"""
        from src.core.puzzle_system import check_puzzles

        # Pre-unlock oregon_trail
        self.save_system.unlock_game("oregon_trail")

        # Set up complete solution
        self.filesystem.set_user('root')
        self.filesystem.change_directory('/usr/local/deprecated')
        self.filesystem.move_file('sys_control.py', '/bin/systemctl')
        self.filesystem.change_directory('/bin')
        self.filesystem.set_permissions('systemctl', '755')

        self.filesystem.change_directory('/etc/systemd/system')
        self.filesystem.create_directory('cooler.service.d')
        self.filesystem.change_directory('cooler.service.d')
        self.filesystem.create_file('override.conf', [
            "[Unit]",
            "Conflicts=laser.service"
        ])

        # Check puzzle
        newly_unlocked = check_puzzles(self.filesystem, self.save_system, "systemctl")

        # Should not unlock again
        self.assertEqual(len(newly_unlocked), 0, "Should not unlock if already unlocked")


if __name__ == '__main__':
    unittest.main()
