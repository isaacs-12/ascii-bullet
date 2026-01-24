"""
Systemd service manager for tracking service states and unit files
"""


class SystemdManager:
    """Manages systemd services and unit files"""
    
    # Critical services that must remain active for system stability
    # If any of these are stopped, the system will reset
    CRITICAL_SERVICES = {
        'blthll.service',  # Main game service - system won't function without it
        'network.service',  # Network service - critical for system operation
    }
    
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
            # Create symlink files for default enabled services
            self._create_default_enabled_symlinks()
        
        # Track if system reset was triggered
        self.system_reset_triggered = False
    
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
        Start a service with dependency and conflict checking.
        Implements puzzle logic: checks Requires, Conflicts, and handles deadlock scenarios.
        
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
        
        # Get effective config (base + drop-in overrides)
        content = self._get_unit_file_content(service_name)
        deps = self._parse_dependencies(content)
        
        # 1. CHECK REQUIREMENTS FIRST
        # Start required services before checking conflicts
        for req_service in deps.get('Requires', []):
            req_state = self.get_service_state(req_service)
            if req_state != 'active':
                # Try to start the required service first
                req_success, req_msg = self.start_service(req_service)
                if not req_success:
                    return (False, f"Dependency failed: {req_service} is not active. {req_msg}")
        
        # 2. CHECK REVERSE CONFLICTS (The Boss Weakness - Puzzle Logic)
        # Check if any required services conflict with this service
        # This is the key: cooler has Conflicts=laser.service (from override)
        # So when laser tries to start, cooler must be stopped
        # But laser requires cooler, creating a deadlock
        for req_service in deps.get('Requires', []):
            # Get the required service's config (including overrides)
            req_content = self._get_unit_file_content(req_service)
            req_deps = self._parse_dependencies(req_content)
            # Check if the required service conflicts with us
            if service_name in req_deps.get('Conflicts', []):
                # The required service conflicts with us!
                # This creates a deadlock: we require it, but it conflicts with us
                # PUZZLE: Special case for laser + cooler
                if service_name == "laser.service" and req_service == "cooler.service":
                    # Stop cooler (it conflicts with laser)
                    self.stop_service(req_service)
                    # Now laser requires cooler, but cooler is stopped = deadlock!
                    return (False, "CRITICAL ERROR: OVERHEAT DETECTED. Laser firing canceled. Boss Vulnerable!")
        
        # 3. CHECK CONFLICTS (this service conflicts with others)
        # Check if this service conflicts with others (we would stop them)
        stopped_critical = False
        for conflict_service in deps.get('Conflicts', []):
            conflict_state = self.get_service_state(conflict_service)
            if conflict_state == 'active':
                # Check if we're about to stop a critical service
                if conflict_service in self.CRITICAL_SERVICES:
                    stopped_critical = True
                # Standard systemd behavior: Stop the conflicting service
                stop_result = self.stop_service(conflict_service)
                # If stopping caused a reset, propagate that
                if not stop_result[0] and self.system_reset_triggered:
                    return stop_result
        
        # 4. Re-check requirements after conflict resolution
        # (In case a required service was stopped due to conflicts)
        for req_service in deps.get('Requires', []):
            req_state = self.get_service_state(req_service)
            if req_state != 'active':
                # If we stopped a critical service that was required, system is unstable
                if stopped_critical:
                    return self._trigger_system_reset(service_name)
                return (False, f"Dependency failed: {req_service} is not active.")
        
        # 5. Check system stability before starting
        if not self._check_system_stability():
            return self._trigger_system_reset(service_name)
        
        # 6. Start the service
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
        
        # Puzzle: shield.service is "masked" and cannot be stopped
        if service_name == "shield.service":
            return (False, f"Failed to stop {service_name}: Unit {service_name} is masked by 'System Integrity Protection'.\nAction forbidden by PID 1.")
        
        current_state = self.get_service_state(service_name)
        if current_state == 'inactive':
            return (True, f"{service_name} is already inactive.")
        
        # Guardrail: Warn heavily if trying to stop critical service
        if service_name in self.CRITICAL_SERVICES:
            # Check if other services depend on this critical service
            dependent_services = self._find_dependent_services(service_name)
            warning_msg = f"WARNING: {service_name} is a critical system service.\n"
            if dependent_services:
                dep_list = ', '.join(dependent_services[:3])  # Show first 3
                if len(dependent_services) > 3:
                    dep_list += f" and {len(dependent_services) - 3} more"
                warning_msg += f"Active services depending on {service_name}: {dep_list}\n"
            warning_msg += "Stopping this service may cause system instability."
            
            # Allow stopping but check stability after
            self.set_service_state(service_name, 'inactive')
            
            # Check if system is still stable
            if not self._check_system_stability():
                # System is unstable - trigger reset
                return self._trigger_system_reset(service_name)
            
            return (True, f"{service_name} stopped successfully.\n{warning_msg}")
        
        # Stop the service
        self.set_service_state(service_name, 'inactive')
        
        # Check system stability after stopping
        if not self._check_system_stability():
            # System became unstable - trigger reset
            return self._trigger_system_reset(service_name)
        
        return (True, f"{service_name} stopped successfully.")
    
    def _find_dependent_services(self, service_name):
        """
        Find all services that require the given service.
        
        Args:
            service_name: Name of the service to check
            
        Returns:
            list: List of service names that depend on this service
        """
        dependent = []
        
        # Check all unit files for dependencies
        unit_files = self.list_unit_files()
        for unit_name, _, _ in unit_files:
            if unit_name == service_name:
                continue
            
            # Get unit content and check if it requires this service
            content = self._get_unit_file_content(unit_name)
            deps = self._parse_dependencies(content)
            
            # Check if this unit requires the service
            if service_name in deps.get('Requires', []):
                # Check if the dependent service is active
                if self.get_service_state(unit_name) == 'active':
                    dependent.append(unit_name)
        
        return dependent
    
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
    
    def _resolve_unit_path(self, service_name):
        """
        Find the path to a unit file, checking in priority order
        
        Args:
            service_name: Name of the service
            
        Returns:
            str: Full path to unit file, or None if not found
        """
        old_pwd = self.filesystem.get_pwd()
        
        # Check /run/systemd/system/ first (runtime, highest priority)
        self.filesystem.change_directory('/run/systemd/system')
        if self.filesystem.file_exists(service_name):
            self.filesystem.change_directory(old_pwd)
            return f'/run/systemd/system/{service_name}'
        
        # Check /etc/systemd/system/ (enabled services, second priority)
        self.filesystem.change_directory('/etc/systemd/system')
        if self.filesystem.file_exists(service_name):
            self.filesystem.change_directory(old_pwd)
            return f'/etc/systemd/system/{service_name}'
        
        # Check /usr/lib/systemd/system/ (installed, lowest priority)
        self.filesystem.change_directory('/usr/lib/systemd/system')
        if self.filesystem.file_exists(service_name):
            self.filesystem.change_directory(old_pwd)
            return f'/usr/lib/systemd/system/{service_name}'
        
        self.filesystem.change_directory(old_pwd)
        return None
    
    def _unit_file_exists(self, service_name):
        """
        Check if a unit file exists in any of the systemd directories
        
        Args:
            service_name: Name of the service
            
        Returns:
            bool: True if unit file exists
        """
        return self._resolve_unit_path(service_name) is not None
    
    def _get_unit_file_content(self, service_name):
        """
        Retrieves the effective configuration of a unit, merging base file with drop-in overrides.
        This implements the drop-in override mechanism: Base file + /etc/systemd/system/[service].d/*.conf
        
        Args:
            service_name: Name of the service
            
        Returns:
            str: Merged unit file content
        """
        # 1. Read Base File
        base_path = self._resolve_unit_path(service_name)
        base_content = ""
        
        if base_path:
            old_pwd = self.filesystem.get_pwd()
            # Navigate to the directory containing the file
            path_parts = base_path.split('/')
            filename = path_parts[-1]
            dir_path = '/' + '/'.join(path_parts[:-1])
            
            self.filesystem.change_directory(dir_path)
            success, content = self.filesystem.read_file(filename)
            if success:
                if isinstance(content, list):
                    base_content = '\n'.join(content)
                else:
                    base_content = str(content)
            self.filesystem.change_directory(old_pwd)
        
        # 2. Look for Drop-in Overrides (e.g., /etc/systemd/system/laser.service.d/*.conf)
        override_dir = f"/etc/systemd/system/{service_name}.d"
        overrides = []
        
        old_pwd = self.filesystem.get_pwd()
        # Check if override directory exists by trying to navigate to it
        success, error = self.filesystem.change_directory(override_dir)
        if success:
            # Directory exists, list files in it
            override_files = self.filesystem.list_directory(show_hidden=True)
            for f in sorted(override_files):
                if f.endswith('.conf') and not f.endswith('/'):
                    success, content = self.filesystem.read_file(f)
                    if success:
                        if isinstance(content, list):
                            overrides.append('\n'.join(str(line) for line in content))
                        else:
                            overrides.append(str(content))
        # Restore original directory
        self.filesystem.change_directory(old_pwd)
        
        # Merge: base content + overrides
        if overrides:
            return base_content + '\n' + '\n'.join(overrides)
        return base_content
    
    def _parse_dependencies(self, content):
        """
        Simple parser to extract Requires, Conflicts, Before, and After lines from unit file content.
        
        Args:
            content: Unit file content as string
            
        Returns:
            dict: Dictionary with keys 'Requires', 'Conflicts', 'Before', 'After', each containing a list of service names
        """
        deps = {'Requires': [], 'Conflicts': [], 'Before': [], 'After': []}
        
        if not content:
            return deps
        
        current_section = None
        for line in content.splitlines():
            line = line.strip()
            
            # Track section headers
            if line.startswith('[') and line.endswith(']'):
                current_section = line[1:-1]
                continue
            
            # Only parse [Unit] section for dependencies
            if current_section != 'Unit':
                continue
            
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Parse key=value pairs
            if '=' in line:
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip()
                
                if key in deps:
                    # Handle space-separated lists (systemd allows multiple services)
                    services = [s.strip() for s in val.split() if s.strip()]
                    # Normalize service names (add .service if missing)
                    normalized = []
                    for svc in services:
                        if not svc.endswith('.service'):
                            svc = svc + '.service'
                        normalized.append(svc)
                    deps[key].extend(normalized)
        
        return deps
    
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
    
    def _create_default_enabled_symlinks(self):
        """Create symlink files in /etc/systemd/system/ for default enabled services"""
        old_pwd = self.filesystem.get_pwd()
        self.filesystem.change_directory('/etc/systemd/system')
        
        for service_name in self.enabled_services:
            # Check if symlink already exists
            if not self.filesystem.file_exists(service_name):
                # Create symlink file
                self.filesystem.create_file(service_name, f"# Symlink to /usr/lib/systemd/system/{service_name}\n")
        
        self.filesystem.change_directory(old_pwd)
    
    def _check_system_stability(self):
        """
        Check if critical services are still running.
        If any critical service is inactive, the system is unstable.
        
        Returns:
            bool: True if system is stable, False if unstable
        """
        for critical_service in self.CRITICAL_SERVICES:
            state = self.get_service_state(critical_service)
            if state != 'active':
                return False
        return True
    
    def _trigger_system_reset(self, failed_service=None):
        """
        Trigger a system reset when critical services fail.
        Resets all service states to defaults and restores enabled services.
        
        Args:
            failed_service: Name of the service that caused the failure (for error message)
            
        Returns:
            tuple: (success: bool, message: str)
        """
        self.system_reset_triggered = True
        
        # Build error message
        if failed_service:
            failed_msg = f"CRITICAL: {failed_service} stopped."
        else:
            failed_msg = "CRITICAL: System instability detected."
        
        # Reset service states to defaults
        self.service_states = {
            'blthll.service': 'active',
            'network.service': 'active',
            'sshd.service': 'inactive',
        }
        
        # Reset enabled services
        self.enabled_services = {'blthll.service', 'network.service'}
        
        # Recreate default symlinks
        self._create_default_enabled_symlinks()
        
        # Save reset state
        if self.save_system:
            self.save_system.save_systemd_states(self.service_states)
            self.save_system.save_systemd_enabled(list(self.enabled_services))
        
        # Return error message
        message = f"*** {failed_msg} ***\n"
        message += "\n"
        message += "CRITICAL SYSTEM FAILURE DETECTED\n"
        message += "==================================\n"
        message += "One or more critical system services have been stopped.\n"
        message += "System integrity compromised. Emergency recovery initiated.\n"
        message += "\n"
        message += "Emergency actions taken:\n"
        message += "  - All service states reset to defaults\n"
        message += "  - Critical services restored\n"
        message += "  - System configuration reset\n"
        message += "\n"
        message += "WARNING: System reboot recommended to ensure stability.\n"
        message += "Some services may need manual intervention to restore full functionality."
        
        return (False, message)
    
    def was_system_reset_triggered(self):
        """
        Check if a system reset was triggered in the last operation.
        Call this after start/stop operations to check if system needs reset.
        
        Returns:
            bool: True if reset was triggered
        """
        return self.system_reset_triggered
    
    def clear_reset_flag(self):
        """Clear the system reset flag (call after handling reset)"""
        self.system_reset_triggered = False
