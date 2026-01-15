"""
Simulated filesystem for terminal easter eggs
"""

import json


class VirtualFileSystem:
    """A virtual filesystem with directories and files"""
    
    # Maximum total size for user-created files (16KB)
    MAX_USER_FILES_SIZE = 16 * 1024
    
    def __init__(self, saved_state=None):
        """
        Initialize the filesystem structure
        
        Args:
            saved_state: Optional saved filesystem state to restore
        """
        # Current directory path as a list (e.g., ['home', 'pilot', 'blthll'])
        self.current_path = ['home', 'pilot', 'blthll']
        
        # Load default filesystem
        self.filesystem = self._get_default_filesystem()
        
        # Track user modifications separately
        self.user_created_files = {}  # path -> content
        self.user_created_dirs = []   # list of paths
        self.user_modified_files = {}  # path -> content
        self.user_deleted_files = set()  # paths of default files that have been deleted/moved
        
        # File permissions: path -> "rwx" string (read, write, execute)
        # Default: "rw-" for most files, "rwx" for .py files
        self.file_permissions = {}  # path -> permission string like "rwx", "rw-", "r--"
        
        # Restore saved state if provided
        if saved_state:
            self._restore_state(saved_state)
    
    def _get_default_filesystem(self):
        """Get the default read-only filesystem structure"""
        return {
            'home': {
                'dirs': {
                    'pilot': {
                        'dirs': {
                            'blthll': {
                                'dirs': {
                                    'weapons': {
                                        'dirs': {},
                                        'files': {
                                            'laser.txt': [
                                                "LASER CANNON v2.4",
                                                "Damage: High",
                                                "Fire Rate: Fast",
                                                "Special: Piercing shots"
                                            ],
                                            'missile.txt': [
                                                "HOMING MISSILES",
                                                "Damage: Very High",
                                                "Fire Rate: Slow",
                                                "Special: Tracks enemies"
                                            ]
                                        }
                                    },
                                    'data': {
                                        'dirs': {
                                            'secret': {
                                                'dirs': {},
                                                'files': {
                                                    'cheat_codes.txt': [
                                                        "SUPER SECRET CHEAT CODES",
                                                        "=======================",
                                                        "Up Up Down Down Left Right Left Right B A",
                                                        "Just kidding, no cheats here!",
                                                        "Git gud at dodging bullets instead."
                                                    ],
                                                    'developer_notes.txt': [
                                                        "TODO: Make bullets less impossible",
                                                        "TODO: Add easy mode (nah)",
                                                        "TODO: Increase bullet speed (yes!)",
                                                        "TODO: Add more particle effects"
                                                    ]
                                                }
                                            }
                                        },
                                        'files': {
                                            'bullets.dat': [
                                                "░▒▓█ BULLET DATA █▓▒░",
                                                "◉ ◎ ● ○ ◐ ◑ ◒ ◓ ◔ ◕",
                                                "",
                                                "Type: Standard",
                                                "Speed: Variable",
                                                "Pattern: Spiral, Linear, Radial"
                                            ],
                                            'highscores.txt': [
                                                "HIGH SCORES",
                                                "===========",
                                                "1. PLAYER1 - 999999",
                                                "2. HACKER  - 123456",
                                                "3. NOOB    - 00042"
                                            ]
                                        }
                                    },
                                    'certain_death': {
                                        'dirs': {},
                                        'files': {
                                            'warning.txt': [
                                                "⚠️  WARNING ⚠️",
                                                "",
                                                "You are entering the CERTAIN DEATH zone.",
                                                "Bullets here are UNAVOIDABLE.",
                                                "Turn back while you still can!",
                                                "",
                                                "...or don't. Your funeral. 💀"
                                            ]
                                        }
                                    }
                                },
                                'files': {
                                    'readme.txt': [
                                        "Welcome to BLTHLL (Bullet Hell)",
                                        "",
                                        "You are a pilot trying to survive.",
                                        "Good luck. You'll need it.",
                                        "",
                                        "Hint: Try exploring with 'ls' and 'cd'!"
                                    ],
                                    'manual.txt': [
                                        "SURVIVAL MANUAL",
                                        "===============",
                                        "Step 1: Don't get hit",
                                        "Step 2: See step 1",
                                        "Step 3: There is no step 3"
                                    ],
                                    'hello_world.py': [
                                        "# Simple test script",
                                        "print('Hello, World!')",
                                    ]
                                }
                            }
                        },
                        'files': {}
                    }
                },
                'files': {}
            },
            'etc': {
                'dirs': {},
                'files': {
                    'motd': [
                        "Welcome to BLTHLL Terminal System",
                        "Unauthorized access will result in more bullets."
                    ]
                }
            }
        }
    
    def get_current_directory(self):
        """Get the current directory object"""
        current = self.filesystem
        for i, dir_name in enumerate(self.current_path):
            if i == 0:
                # First level: directly in filesystem
                if dir_name in current:
                    current = current[dir_name]
                else:
                    return self.filesystem
            else:
                # Subsequent levels: navigate through 'dirs'
                if 'dirs' in current and dir_name in current['dirs']:
                    current = current['dirs'][dir_name]
                else:
                    return self.filesystem
        return current
    
    def get_pwd(self):
        """Get current working directory as string"""
        return '/' + '/'.join(self.current_path)
    
    def list_directory(self):
        """List contents of current directory"""
        current_dir = self.get_current_directory()
        contents = []
        
        # Add directories
        if 'dirs' in current_dir:
            for dir_name in sorted(current_dir['dirs'].keys()):
                contents.append(f"{dir_name}/")
        
        # Add files
        if 'files' in current_dir:
            for file_name in sorted(current_dir['files'].keys()):
                contents.append(file_name)
        
        return contents
    
    def change_directory(self, path):
        """
        Change directory
        
        Args:
            path: Directory path (e.g., 'data', '..', '/home/pilot')
            
        Returns:
            tuple: (success: bool, error_message: str or None)
        """
        if path == '..':
            # Go to parent directory
            if len(self.current_path) > 1:
                self.current_path.pop()
                return (True, None)
            else:
                return (False, "Already at root directory")
        
        elif path == '/' or path == '~':
            # Go to home
            self.current_path = ['home', 'pilot', 'blthll']
            return (True, None)
        
        elif path.startswith('/'):
            # Absolute path
            parts = [p for p in path.split('/') if p]
            if self._directory_exists(parts):
                self.current_path = parts
                return (True, None)
            else:
                return (False, f"cd: {path}: No such directory")
        
        else:
            # Relative path
            new_path = self.current_path + [path]
            if self._directory_exists(new_path):
                self.current_path = new_path
                return (True, None)
            else:
                return (False, f"cd: {path}: No such directory")
    
    def _directory_exists(self, path_list):
        """Check if a directory path exists"""
        current = self.filesystem
        for i, dir_name in enumerate(path_list):
            if i == 0:
                # First level: directly in filesystem
                if dir_name in current:
                    current = current[dir_name]
                else:
                    return False
            else:
                # Subsequent levels: navigate through 'dirs'
                if 'dirs' in current and dir_name in current['dirs']:
                    current = current['dirs'][dir_name]
                else:
                    return False
        return True
    
    def read_file(self, filename):
        """
        Read a file from the current directory
        
        Args:
            filename: Name of the file to read
            
        Returns:
            tuple: (success: bool, content: list of strings or error message)
        """
        current_dir = self.get_current_directory()
        
        if 'files' in current_dir and filename in current_dir['files']:
            content = current_dir['files'][filename]
            if isinstance(content, list):
                return (True, content)
            else:
                return (True, [content])
        else:
            return (False, f"cat: {filename}: No such file")
    
    def file_exists(self, filename):
        """Check if a file exists in the current directory"""
        full_path = self.get_pwd() + '/' + filename
        
        # Check if file has been deleted
        if full_path in self.user_deleted_files:
            return False
        
        current_dir = self.get_current_directory()
        if 'files' in current_dir and filename in current_dir['files']:
            return True
        
        # Check user-created files
        return full_path in self.user_created_files or full_path in self.user_modified_files
    
    # === Mutable Filesystem Operations ===
    
    def _get_user_files_size(self):
        """Calculate total size of user-created content"""
        total = 0
        for content in self.user_created_files.values():
            if isinstance(content, list):
                total += sum(len(line) for line in content)
            else:
                total += len(content)
        for content in self.user_modified_files.values():
            if isinstance(content, list):
                total += sum(len(line) for line in content)
            else:
                total += len(content)
        return total
    
    def create_file(self, filename, content=""):
        """
        Create a new file in current directory
        
        Args:
            filename: Name of file to create
            content: Initial content (string or list of strings)
            
        Returns:
            tuple: (success, error_message or None)
        """
        if self.file_exists(filename):
            return (False, f"File '{filename}' already exists")
        
        # Check size limit
        content_size = len(content) if isinstance(content, str) else sum(len(line) for line in content)
        if self._get_user_files_size() + content_size > self.MAX_USER_FILES_SIZE:
            return (False, "File size limit exceeded (16KB max for user files)")
        
        full_path = self.get_pwd() + '/' + filename
        self.user_created_files[full_path] = content if content else []
        return (True, None)
    
    def write_file(self, filename, content, append=False):
        """
        Write content to a file (overwrites or appends)
        
        Args:
            filename: Name of file
            content: Content to write (string)
            append: If True, append instead of overwrite
            
        Returns:
            tuple: (success, error_message or None)
        """
        full_path = self.get_pwd() + '/' + filename
        
        # Check write permission for existing files
        if self.file_exists(filename):
            if not self.check_permission(filename, 'w'):
                return (False, f"Permission denied: '{filename}'")
        
        # Get existing content
        existing = None
        if full_path in self.user_created_files:
            existing = self.user_created_files[full_path]
        elif full_path in self.user_modified_files:
            existing = self.user_modified_files[full_path]
        elif self.file_exists(filename):
            # Modifying a default file
            success, file_content = self.read_file(filename)
            if success:
                existing = file_content
        
        # Build new content
        if append and existing:
            if isinstance(existing, list):
                new_content = existing + [content]
            else:
                new_content = existing + '\n' + content
        else:
            new_content = [content] if not isinstance(content, list) else content
        
        # Check size
        new_size = sum(len(line) for line in new_content) if isinstance(new_content, list) else len(new_content)
        if self._get_user_files_size() + new_size > self.MAX_USER_FILES_SIZE:
            return (False, "File size limit exceeded (16KB max for user files)")
        
        # Write to appropriate location
        if full_path in self.user_created_files:
            self.user_created_files[full_path] = new_content
        else:
            self.user_modified_files[full_path] = new_content
        
        return (True, None)
    
    def delete_file(self, filename):
        """
        Delete a file from current directory
        
        Args:
            filename: Name of file to delete
            
        Returns:
            tuple: (success, error_message or None)
        """
        full_path = self.get_pwd() + '/' + filename
        
        # Check write permission (needed to delete)
        if not self.check_permission(filename, 'w'):
            return (False, f"Permission denied: '{filename}'")
        
        # Delete user-created files
        if full_path in self.user_created_files:
            del self.user_created_files[full_path]
            return (True, None)
        elif full_path in self.user_modified_files:
            del self.user_modified_files[full_path]
            return (True, None)
        elif self.file_exists(filename):
            # Mark default file as deleted (can be undone with rm save)
            self.user_deleted_files.add(full_path)
            return (True, None)
        else:
            return (False, f"File '{filename}' not found")
    
    def create_directory(self, dirname):
        """
        Create a new directory in current location
        
        Args:
            dirname: Name of directory to create
            
        Returns:
            tuple: (success, error_message or None)
        """
        current_dir = self.get_current_directory()
        if 'dirs' in current_dir and dirname in current_dir['dirs']:
            return (False, f"Directory '{dirname}' already exists")
        
        full_path = self.get_pwd() + '/' + dirname
        if full_path in self.user_created_dirs:
            return (False, f"Directory '{dirname}' already exists")
        
        self.user_created_dirs.append(full_path)
        return (True, None)
    
    def delete_directory(self, dirname):
        """
        Delete an empty user-created directory
        
        Args:
            dirname: Name of directory to delete
            
        Returns:
            tuple: (success, error_message or None)
        """
        full_path = self.get_pwd() + '/' + dirname
        
        if full_path not in self.user_created_dirs:
            return (False, f"Cannot delete: not a user-created directory")
        
        # Check if empty
        for file_path in self.user_created_files:
            if file_path.startswith(full_path + '/'):
                return (False, f"Directory not empty")
        
        self.user_created_dirs.remove(full_path)
        return (True, None)
    
    def get_permissions(self, filename):
        """
        Get file permissions
        
        Args:
            filename: Name of file
            
        Returns:
            str: Permission string like "rwx", "rw-", "r--", or None if file doesn't exist
        """
        full_path = self.get_pwd() + '/' + filename
        
        # Check if file exists
        if not self.file_exists(filename):
            return None
        
        # Return custom permissions if set
        if full_path in self.file_permissions:
            return self.file_permissions[full_path]
        
        # Default permissions based on file type
        if filename.endswith('.py'):
            return "rwx"  # Python files are executable by default
        else:
            return "rw-"  # Regular files are read-write by default
    
    def set_permissions(self, filename, permissions):
        """
        Set file permissions
        
        Args:
            filename: Name of file
            permissions: Permission string like "rwx", "rw-", "r--", or octal like "755"
            
        Returns:
            tuple: (success, error_message or None)
        """
        full_path = self.get_pwd() + '/' + filename
        
        # Check if file exists
        if not self.file_exists(filename):
            return (False, f"chmod: cannot access '{filename}': No such file or directory")
        
        # Parse permissions
        if permissions.isdigit() and len(permissions) == 3:
            # Octal format (e.g., "644", "755")
            try:
                mode = int(permissions[2])  # Just use the user permissions for simplicity
                perm_str = ""
                perm_str += "r" if mode & 4 else "-"
                perm_str += "w" if mode & 2 else "-"
                perm_str += "x" if mode & 1 else "-"
                permissions = perm_str
            except ValueError:
                return (False, f"chmod: invalid mode: '{permissions}'")
        elif len(permissions) == 3 and all(c in 'rwx-' for c in permissions):
            # Symbolic format (e.g., "rwx", "rw-", "r--")
            pass
        else:
            return (False, f"chmod: invalid mode: '{permissions}'")
        
        # Set permissions
        self.file_permissions[full_path] = permissions
        return (True, None)
    
    def check_permission(self, filename, permission):
        """
        Check if user has a specific permission on a file
        
        Args:
            filename: Name of file
            permission: 'r' for read, 'w' for write, 'x' for execute
            
        Returns:
            bool: True if permission is granted, False otherwise
        """
        perms = self.get_permissions(filename)
        if perms is None:
            return False
        
        perm_map = {'r': 0, 'w': 1, 'x': 2}
        if permission not in perm_map:
            return False
        
        return perms[perm_map[permission]] == permission
    
    def move_file(self, source, destination):
        """
        Move or rename a file (including default system files)
        
        Args:
            source: Source filename (in current directory)
            destination: Destination path (can include directory path or just filename)
            
        Returns:
            tuple: (success, error_message or None)
        """
        current_pwd = self.get_pwd()
        source_full = current_pwd + '/' + source
        
        # Check if source exists
        if not self.file_exists(source):
            return (False, f"File '{source}' not found")
        
        # Read source file content
        success, content = self.read_file(source)
        if not success:
            return (False, f"Cannot read source file: {source}")
        
        # Compute destination full path
        if '/' in destination:
            # Destination includes directory path
            dest_parts = destination.rsplit('/', 1)
            dest_dir = dest_parts[0]
            dest_filename = dest_parts[1]
            
            # Validate destination directory exists
            old_path = self.current_path[:]
            success, error = self.change_directory(dest_dir)
            if not success:
                self.current_path = old_path
                return (False, f"Destination directory not found: {dest_dir}")
            
            dest_full = self.get_pwd() + '/' + dest_filename
            self.current_path = old_path
            
            # Check if destination file already exists
            old_path = self.current_path[:]
            self.change_directory(dest_dir)
            dest_exists = self.file_exists(dest_filename)
            self.current_path = old_path
            
            if dest_exists:
                return (False, f"Destination file already exists: {destination}")
        else:
            # Destination is in current directory (rename)
            dest_full = current_pwd + '/' + destination
            if self.file_exists(destination):
                return (False, f"Destination file already exists: {destination}")
        
        # Determine if source is a default file
        is_default = (source_full not in self.user_created_files and 
                     source_full not in self.user_modified_files)
        
        # Perform the move
        if source_full in self.user_created_files:
            del self.user_created_files[source_full]
        elif source_full in self.user_modified_files:
            del self.user_modified_files[source_full]
        elif is_default:
            # Mark default file as deleted from source location
            self.user_deleted_files.add(source_full)
        
        # Create file at destination
        self.user_created_files[dest_full] = content
        
        return (True, None)
    
    def list_directory(self):
        """List contents of current directory (including user-created)"""
        current_dir = self.get_current_directory()
        contents = []
        current_path = self.get_pwd()
        
        # Add default directories
        if 'dirs' in current_dir:
            for dir_name in sorted(current_dir['dirs'].keys()):
                contents.append(f"{dir_name}/")
        
        # Add user-created directories
        for dir_path in sorted(self.user_created_dirs):
            # Check if it's a direct child of current directory
            if '/' in dir_path:
                parent = dir_path.rsplit('/', 1)[0]
                if parent == current_path:
                    dir_name = dir_path.rsplit('/', 1)[1]
                    if f"{dir_name}/" not in contents:
                        contents.append(f"{dir_name}/")
        
        # Add default files (excluding deleted ones)
        if 'files' in current_dir:
            for file_name in sorted(current_dir['files'].keys()):
                full_path = current_path + '/' + file_name
                if full_path not in self.user_deleted_files:
                    contents.append(file_name)
        
        # Add user-created files in this directory
        for file_path in sorted(self.user_created_files.keys()):
            if '/' in file_path:
                parent = file_path.rsplit('/', 1)[0]
                if parent == current_path:
                    file_name = file_path.rsplit('/', 1)[1]
                    if file_name not in contents:
                        contents.append(file_name)
        
        # Add user-modified files
        for file_path in sorted(self.user_modified_files.keys()):
            if '/' in file_path:
                parent = file_path.rsplit('/', 1)[0]
                if parent == current_path:
                    file_name = file_path.rsplit('/', 1)[1]
                    if file_name not in contents:
                        contents.append(file_name)
        
        return contents
    
    def read_file(self, filename):
        """Read a file (checks user files first, then defaults)"""
        full_path = self.get_pwd() + '/' + filename
        
        # Check if file has been deleted
        if full_path in self.user_deleted_files:
            return (False, f"File '{filename}' not found")
        
        # Check read permission
        if not self.check_permission(filename, 'r'):
            return (False, f"Permission denied: '{filename}'")
        
        # Check user-modified files first
        if full_path in self.user_modified_files:
            content = self.user_modified_files[full_path]
            if isinstance(content, list):
                return (True, content)
            else:
                return (True, [content])
        
        # Check user-created files
        if full_path in self.user_created_files:
            content = self.user_created_files[full_path]
            if isinstance(content, list):
                return (True, content)
            else:
                return (True, [content])
        
        # Fall back to default files
        current_dir = self.get_current_directory()
        
        if 'files' in current_dir and filename in current_dir['files']:
            content = current_dir['files'][filename]
            if isinstance(content, list):
                return (True, content)
            else:
                return (True, [content])
        else:
            return (False, f"cat: {filename}: No such file")
    
    # === Save/Load State ===
    
    def get_state(self):
        """Get filesystem state for saving"""
        return {
            'current_path': self.current_path,
            'user_created_files': self.user_created_files,
            'user_created_dirs': self.user_created_dirs,
            'user_modified_files': self.user_modified_files,
            'user_deleted_files': list(self.user_deleted_files),
            'file_permissions': self.file_permissions
        }
    
    def _restore_state(self, state):
        """Restore filesystem state from save"""
        if 'current_path' in state:
            self.current_path = state['current_path']
        if 'user_created_files' in state:
            self.user_created_files = state['user_created_files']
        if 'user_created_dirs' in state:
            self.user_created_dirs = state['user_created_dirs']
        if 'user_modified_files' in state:
            self.user_modified_files = state['user_modified_files']
        if 'user_deleted_files' in state:
            self.user_deleted_files = set(state['user_deleted_files'])
        if 'file_permissions' in state:
            self.file_permissions = state['file_permissions']
    
    def reset_to_defaults(self):
        """Reset filesystem to default state"""
        self.current_path = ['home', 'pilot', 'blthll']
        self.user_created_files = {}
        self.user_created_dirs = []
        self.user_modified_files = {}
        self.user_deleted_files = set()
        self.file_permissions = {}

