"""
Systemd service manager for tracking service states and unit files
"""


class SystemdManager:
    """Manages systemd services and unit files"""
    
    def __init__(self, filesystem, save_system=None):
        """
        Initialize systemd manager
        
        Args:
            filesystem: VirtualFileSystem instance
            save_system: Optional SaveSystem instance for persistence
        """
        self.filesystem = filesystem
        self.save_system = save_system
        
        # Service states: 'active', 'inactive', 'failed', 'activating', 'deactivating'
        # Load from save or initialize defaults
        saved_states = save_system.get_systemd_states() if save_system else None
        if saved_states:
            self.service_states = saved_states
        else:
            # Default states for services
            self.service_states = {
                'blthll.service': 'active',
                'network.service': 'active',
                'sshd.service': 'inactive',
            }
        
        # Enabled services (symlinks in /etc/systemd/system/)
        saved_enabled = save_system.get_systemd_enabled() if save_system else None
        if saved_enabled:
            self.enabled_services = set(saved_enabled)
        else:
            # Default enabled services
            self.enabled_services = {'blthll.service', 'network.service'}
    
    def get_service_state(self, service_name):
        """
        Get the current state of a service
        
        Args:
            service_name: Name of the service (e.g., 'blthll.service')
            
        Returns:
            str: Service state ('active', 'inactive', 'failed', etc.)
        """
        # Normalize service name (add .service if not present)
        if not service_name.endswith('.service'):
            service_name = service_name + '.service'
        
        return self.service_states.get(service_name, 'inactive')
    
    def set_service_state(self, service_name, state):
        """
        Set the state of a service
        
        Args:
            service_name: Name of the service
            state: New state ('active', 'inactive', 'failed', etc.)
        """
        # Normalize service name
        if not service_name.endswith('.service'):
            service_name = service_name + '.service'
        
        self.service_states[service_name] = state
        
        # Save state if save system is available
        if self.save_system:
            self.save_system.save_systemd_states(self.service_states)
    
    def start_service(self, service_name):
        """
        Start a service
        
        Args:
            service_name: Name of the service
            
        Returns:
            tuple: (success: bool, message: str)
        """
        # Normalize service name
        if not service_name.endswith('.service'):
            service_name = service_name + '.service'
        
        # Check if unit file exists
        if not self._unit_file_exists(service_name):
            return (False, f"Unit {service_name} not found.")
        
        current_state = self.get_service_state(service_name)
        if current_state == 'active':
            return (True, f"{service_name} is already active.")
        
        # Start the service
        self.set_service_state(service_name, 'active')
        return (True, f"{service_name} started successfully.")
    
    def stop_service(self, service_name):
        """
        Stop a service
        
        Args:
            service_name: Name of the service
            
        Returns:
            tuple: (success: bool, message: str)
        """
        # Normalize service name
        if not service_name.endswith('.service'):
            service_name = service_name + '.service'
        
        current_state = self.get_service_state(service_name)
        if current_state == 'inactive':
            return (True, f"{service_name} is already inactive.")
        
        # Stop the service
        self.set_service_state(service_name, 'inactive')
        return (True, f"{service_name} stopped successfully.")
    
    def enable_service(self, service_name):
        """
        Enable a service (create symlink in /etc/systemd/system/)
        
        Args:
            service_name: Name of the service
            
        Returns:
            tuple: (success: bool, message: str)
        """
        # Normalize service name
        if not service_name.endswith('.service'):
            service_name = service_name + '.service'
        
        # Check if unit file exists in /usr/lib/systemd/system/
        if not self._unit_file_exists(service_name):
            return (False, f"Unit file {service_name} not found.")
        
        # Check if already enabled
        if service_name in self.enabled_services:
            return (True, f"{service_name} is already enabled.")
        
        # Create symlink (simulated by creating a file in /etc/systemd/system/)
        # In a real system, this would be a symlink, but we'll simulate it
        etc_path = f"/etc/systemd/system/{service_name}"
        old_pwd = self.filesystem.get_pwd()
        
        # Change to /etc/systemd/system/
        self.filesystem.change_directory('/etc/systemd/system')
        
        # Create a file that represents the symlink
        # We'll store it as a special file that indicates it's a symlink
        success, error = self.filesystem.create_file(service_name, f"# Symlink to /usr/lib/systemd/system/{service_name}\n")
        
        # Restore directory
        self.filesystem.change_directory(old_pwd)
        
        if not success:
            return (False, f"Failed to enable {service_name}: {error}")
        
        # Mark as enabled
        self.enabled_services.add(service_name)
        
        # Save enabled services if save system is available
        if self.save_system:
            self.save_system.save_systemd_enabled(list(self.enabled_services))
        
        return (True, f"{service_name} enabled successfully.")
    
    def disable_service(self, service_name):
        """
        Disable a service (remove symlink from /etc/systemd/system/)
        
        Args:
            service_name: Name of the service
            
        Returns:
            tuple: (success: bool, message: str)
        """
        # Normalize service name
        if not service_name.endswith('.service'):
            service_name = service_name + '.service'
        
        # Check if enabled
        if service_name not in self.enabled_services:
            return (True, f"{service_name} is already disabled.")
        
        # Remove symlink (delete file from /etc/systemd/system/)
        etc_path = f"/etc/systemd/system/{service_name}"
        old_pwd = self.filesystem.get_pwd()
        
        # Change to /etc/systemd/system/
        self.filesystem.change_directory('/etc/systemd/system')
        
        # Delete the symlink file
        success, error = self.filesystem.delete_file(service_name)
        
        # Restore directory
        self.filesystem.change_directory(old_pwd)
        
        if not success:
            return (False, f"Failed to disable {service_name}: {error}")
        
        # Mark as disabled
        self.enabled_services.discard(service_name)
        
        # Save enabled services if save system is available
        if self.save_system:
            self.save_system.save_systemd_enabled(list(self.enabled_services))
        
        return (True, f"{service_name} disabled successfully.")
    
    def is_enabled(self, service_name):
        """
        Check if a service is enabled
        
        Args:
            service_name: Name of the service
            
        Returns:
            bool: True if enabled, False otherwise
        """
        # Normalize service name
        if not service_name.endswith('.service'):
            service_name = service_name + '.service'
        
        return service_name in self.enabled_services
    
    def _unit_file_exists(self, service_name):
        """
        Check if a unit file exists in any of the systemd directories
        
        Args:
            service_name: Name of the service
            
        Returns:
            bool: True if unit file exists
        """
        # Check /run/systemd/system/ first (runtime, highest priority)
        old_pwd = self.filesystem.get_pwd()
        
        # Check /run/systemd/system/
        self.filesystem.change_directory('/run/systemd/system')
        if self.filesystem.file_exists(service_name):
            self.filesystem.change_directory(old_pwd)
            return True
        
        # Check /etc/systemd/system/ (enabled services, second priority)
        self.filesystem.change_directory('/etc/systemd/system')
        if self.filesystem.file_exists(service_name):
            self.filesystem.change_directory(old_pwd)
            return True
        
        # Check /usr/lib/systemd/system/ (installed, lowest priority)
        self.filesystem.change_directory('/usr/lib/systemd/system')
        exists = self.filesystem.file_exists(service_name)
        self.filesystem.change_directory(old_pwd)
        
        return exists
    
    def list_unit_files(self):
        """
        List all unit files from all systemd directories
        
        Returns:
            list: List of (service_name, location, enabled) tuples
        """
        unit_files = []
        old_pwd = self.filesystem.get_pwd()
        
        # Check /usr/lib/systemd/system/ (installed)
        self.filesystem.change_directory('/usr/lib/systemd/system')
        files = self.filesystem.list_directory(show_hidden=True)
        for f in files:
            if f.endswith('.service'):
                unit_files.append((f, '/usr/lib/systemd/system/', self.is_enabled(f)))
        
        # Check /run/systemd/system/ (runtime)
        self.filesystem.change_directory('/run/systemd/system')
        files = self.filesystem.list_directory(show_hidden=True)
        for f in files:
            if f.endswith('.service') and f not in [u[0] for u in unit_files]:
                unit_files.append((f, '/run/systemd/system/', self.is_enabled(f)))
        
        # Check /etc/systemd/system/ (enabled)
        self.filesystem.change_directory('/etc/systemd/system')
        files = self.filesystem.list_directory(show_hidden=True)
        for f in files:
            if f.endswith('.service') and f not in [u[0] for u in unit_files]:
                unit_files.append((f, '/etc/systemd/system/', True))
        
        self.filesystem.change_directory(old_pwd)
        
        return unit_files
    
    def list_units(self):
        """
        List all active units with their states
        
        Returns:
            list: List of (service_name, state, enabled) tuples
        """
        units = []
        
        # Get all unit files
        unit_files = self.list_unit_files()
        service_names = {f[0] for f in unit_files}
        
        # Add services that have states but might not have unit files yet
        for service_name in self.service_states.keys():
            if service_name not in service_names:
                service_names.add(service_name)
        
        # Build list with states
        for service_name in sorted(service_names):
            state = self.get_service_state(service_name)
            enabled = self.is_enabled(service_name)
            units.append((service_name, state, enabled))
        
        return units
