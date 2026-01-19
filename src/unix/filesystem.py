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
        
        # File permissions: path -> permission string
        # Can be 3 characters (user only: "rwx") or 9 characters (user, group, other: "rwxrwxrwx")
        # Default: "rw-" for most files, "rwx" for .py files
        self.file_permissions = {}  # path -> permission string like "rwx" or "rwxrwxrwx"
        
        # Default permissions for specific files in the default filesystem
        self.default_file_permissions = self._get_default_file_permissions()
        
        # File ownership system
        self.current_user = "pilot"  # Current user (can be "pilot" or "root")
        self.default_file_owners = self._get_default_file_owners()
        
        # Restore saved state if provided
        if saved_state:
            self._restore_state(saved_state)
    
    def _get_default_file_permissions(self):
        """
        Define default permissions for specific files in the default filesystem.
        Files not listed here will use extension-based defaults (.py = rwx, others = rw-)
        
        Returns:
            dict: path -> permission string
        """
        return {
            # Example: A locked Python script that needs to be made executable
            '/home/pilot/blthll/hello_world.py': 'rw-',
            
            # Example: Read-only files
            '/home/pilot/blthll/data/highscores.txt': 'r--',
            
            # Root-owned system file (no permissions for pilot - needs sudo)
            '/system/core/init.py': '---',
        }
    
    def _get_default_file_owners(self):
        """
        Define file ownership for the default filesystem.
        Files not listed are owned by the current user (pilot).
        
        Returns:
            dict: path -> owner username
        """
        return {
            # System files owned by root
            '/system': 'root',
            '/system/core': 'root',
            '/system/core/init.py': 'root',
        }
    
    def _get_default_filesystem(self):
        """Get the default read-only filesystem structure"""
        return {
            'home': {
                'dirs': {
                    'pilot': {
                        'dirs': {
                            'blthll': {
                                'dirs': {
                                    'data': {
                                        'dirs': {
                                            'secret': {
                                                'dirs': {},
                                                'files': {
                                                    'cheat_codes.txt': [
                                                        "SUPER SECRET CHEAT CODES",
                                                        "=======================",
                                                        "Up Up Down Down Left Right Left Right B A",
                                                    ],
                                                    'developer_notes.txt': [
                                                        "TODO: Add more particle effects",
                                                        "",
                                                        "TODO: System running slow lately -- figure out why..."
                                                    ]
                                                }
                                            },
                                        'files': {
                                            'highscores.txt': [
                                                "DEV HIGH SCORES",
                                                "===========",
                                                "1. PLAYER1 - 999999",
                                                "2. HACKER  - 123456",
                                                "3. WALLY   - 000042"
                                            ]
                                        }
                                    },
                                },
                                'files': {
                                    'readme.txt': [
                                        "Welcome to BLTHLL",
                                        "",
                                        "Hints:",
                                        "- Try exploring with 'ls' and 'cd'",
                                        "- Type 'help' to see available commands",
                                    ],
                                    'manual.txt': [
                                        "SURVIVAL MANUAL",
                                        "===============",
                                        "Step 1: Don't get hit",
                                        "Step 2: See step 1",
                                        "Step 3: There is no step 3",
                                        "",
                                        "SYSTEM COMMANDS",
                                        "===============",
                                        "top - Interactive process monitor (q to quit)",
                                        "ps - Static process list",
                                        "kill <pid> - Terminate a process by PID",
                                        "",
                                        "Tip: Watch for processes with high CPU usage.",
                                        "Something might be draining system resources..."
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
            },
            'system': {
                'dirs': {
                    'core': {
                        'dirs': {},
                        'files': {
                            'init.py': [
                                "#!/usr/bin/env python3",
                                "# BLTHLL System Initialization Script",
                                "# WARNING: This file is owned by root",
                                "# Modifications require elevated privileges",
                                "",
                                "def initialize_system():",
                                "    print('Initializing BLTHLL core systems...')",
                                "    print('[OK] All systems operational')",
                                "",
                                "if __name__ == '__main__':",
                                "    initialize_system()",
                            ]
                        }
                    }
                },
                'files': {}
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
            if len(self.current_path) > 0:
                self.current_path.pop()
                return (True, None)
            else:
                return (False, "Already at root directory")
        
        elif path == '/':
            # Go to root directory
            self.current_path = []
            return (True, None)
        
        elif path == '~':
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
    
    def file_exists(self, filename):
        """
        Check if a file exists in the current directory
        
        Args:
            filename: Name of file to check
            
        Returns:
            bool: True if file exists, False otherwise
        """
        full_path = self.get_pwd() + '/' + filename
        
        # Check if it's been deleted
        if full_path in self.user_deleted_files:
            return False
        
        # Check user-created files
        if full_path in self.user_created_files:
            return True
        
        # Check user-modified files
        if full_path in self.user_modified_files:
            return True
        
        # Check default files
        current_dir = self.get_current_directory()
        if 'files' in current_dir and filename in current_dir['files']:
            return True
        
        return False
    
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
        # Ensure trailing slash for directories
        if not full_path.endswith('/'):
            full_path = full_path + '/'
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
            str: Permission string like "rwx" (3 chars) or "rwxrwxrwx" (9 chars), or None if file doesn't exist
        """
        full_path = self.get_pwd() + '/' + filename
        
        # Check if file exists
        if not self.file_exists(filename):
            return None
        
        # Return custom permissions if set by user (via chmod)
        if full_path in self.file_permissions:
            return self.file_permissions[full_path]
        
        # Check for default permissions defined for this specific file
        if full_path in self.default_file_permissions:
            return self.default_file_permissions[full_path]
        
        # Fall back to extension-based defaults
        if filename.endswith('.py'):
            return "rwx"  # Python files are executable by default
        else:
            return "rw-"  # Regular files are read-write by default
    
    def get_file_owner(self, filename):
        """
        Get the owner of a file or directory
        
        Args:
            filename: Name of file or directory (may have trailing / for dirs)
            
        Returns:
            str: Owner username ("pilot" or "root"), or current user if not specified
        """
        # Strip trailing slash if present (for directories)
        name = filename.rstrip('/')
        full_path = self.get_pwd() + '/' + name
        
        # Normalize double slashes at root
        full_path = full_path.replace('//', '/')
        
        # Check if file has a defined owner
        if full_path in self.default_file_owners:
            return self.default_file_owners[full_path]
        
        # Default: files are owned by the current user
        return self.current_user
    
    def set_user(self, username):
        """
        Set the current user (for sudo implementation)
        
        Args:
            username: "pilot" or "root"
        """
        self.current_user = username
    
    def get_current_user(self):
        """Get the current username"""
        return self.current_user
    
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
        
        # Check ownership (only root or owner can chmod)
        owner = self.get_file_owner(filename)
        if self.current_user != "root" and self.current_user != owner:
            return (False, f"chmod: changing permissions of '{filename}': Operation not permitted")
        
        # Parse permissions
        if permissions.isdigit():
            # Octal format (e.g., "644", "755", "0755", "7", "777")
            try:
                # Handle 4-digit octal (leading 0) or 3-digit or single digit
                if len(permissions) == 4 and permissions[0] == '0':
                    # 4-digit octal like "0755" - use the 3 digits after the leading 0
                    # Parse all three: user, group, other
                    user_mode = int(permissions[1])
                    group_mode = int(permissions[2])
                    other_mode = int(permissions[3])
                    
                    def mode_to_str(mode):
                        s = ""
                        s += "r" if mode & 4 else "-"
                        s += "w" if mode & 2 else "-"
                        s += "x" if mode & 1 else "-"
                        return s
                    
                    permissions = mode_to_str(user_mode) + mode_to_str(group_mode) + mode_to_str(other_mode)
                elif len(permissions) == 1:
                    # Single digit - treat as user permissions only (3 characters)
                    mode = int(permissions)
                    perm_str = ""
                    perm_str += "r" if mode & 4 else "-"
                    perm_str += "w" if mode & 2 else "-"
                    perm_str += "x" if mode & 1 else "-"
                    permissions = perm_str
                elif len(permissions) == 3:
                    # 3-digit octal: user, group, other - create full 9-character string
                    user_mode = int(permissions[0])
                    group_mode = int(permissions[1])
                    other_mode = int(permissions[2])
                    
                    def mode_to_str(mode):
                        s = ""
                        s += "r" if mode & 4 else "-"
                        s += "w" if mode & 2 else "-"
                        s += "x" if mode & 1 else "-"
                        return s
                    
                    permissions = mode_to_str(user_mode) + mode_to_str(group_mode) + mode_to_str(other_mode)
                else:
                    return (False, f"chmod: invalid mode: '{permissions}' (must be 1-4 digits)")
            except (ValueError, IndexError):
                return (False, f"chmod: invalid mode: '{permissions}'")
        elif len(permissions) == 3 and all(c in 'rwx-' for c in permissions):
            # Symbolic format (e.g., "rwx", "rw-", "r--") - 3 characters, user only
            pass
        elif len(permissions) == 9 and all(c in 'rwx-' for c in permissions):
            # Full 9-character format (e.g., "rwxrwxrwx")
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
        # If file doesn't exist, we can't check permissions
        # Return False to be safe (caller should check file_exists first)
        if not self.file_exists(filename):
            return False
        
        perms = self.get_permissions(filename)
        if perms is None:
            return False
        
        perm_map = {'r': 0, 'w': 1, 'x': 2}
        if permission not in perm_map:
            return False
        
        perm_index = perm_map[permission]
        
        # Determine which permission set to check based on user's relationship to file
        owner = self.get_file_owner(filename)
        
        # Root always has all permissions
        if self.current_user == "root":
            return True
        
        # Check which permission group applies
        if len(perms) == 9:
            # 9-character format: user, group, other
            if self.current_user == owner:
                # User is owner - check user permissions (positions 0-2)
                check_index = perm_index
            else:
                # For simplicity, if not owner, check other permissions (positions 6-8)
                # In a full system, we'd check group membership first
                check_index = 6 + perm_index
        else:
            # 3-character format: only user permissions
            # If user is owner, check permissions; otherwise deny
            if self.current_user == owner:
                check_index = perm_index
            else:
                return False
        
        # Check if permission is granted
        if check_index >= len(perms):
            return False
        return perms[check_index] == permission
    
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
        
        # Special case: at root directory
        if len(self.current_path) == 0:
            # At root, directories are top-level keys
            for dir_name in sorted(current_dir.keys()):
                contents.append(f"{dir_name}/")
            return contents
        
        # Add default directories
        if 'dirs' in current_dir:
            for dir_name in sorted(current_dir['dirs'].keys()):
                # Skip metadata keys that might have been incorrectly added as directories
                if dir_name not in ('files', 'dirs'):
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
        
        # Check user-modified files first
        if full_path in self.user_modified_files:
            # Check read permission for existing files
            if not self.check_permission(filename, 'r'):
                return (False, f"Permission denied: '{filename}'")
            content = self.user_modified_files[full_path]
            if isinstance(content, list):
                return (True, content)
            else:
                return (True, [content])
        
        # Check user-created files
        if full_path in self.user_created_files:
            # Check read permission for existing files
            if not self.check_permission(filename, 'r'):
                return (False, f"Permission denied: '{filename}'")
            content = self.user_created_files[full_path]
            if isinstance(content, list):
                return (True, content)
            else:
                return (True, [content])
        
        # Fall back to default files
        current_dir = self.get_current_directory()
        
        if 'files' in current_dir and filename in current_dir['files']:
            # Check read permission for existing default files
            if not self.check_permission(filename, 'r'):
                return (False, f"Permission denied: '{filename}'")
            content = current_dir['files'][filename]
            if isinstance(content, list):
                return (True, content)
            else:
                return (True, [content])
        else:
            # File doesn't exist - don't check permissions for non-existent files
            return (False, f"cat: {filename}: No such file")
    
    # === Save/Load State ===
    
    def get_state(self):
        """Get filesystem state for saving"""
        return {
            # Note: current_path is NOT saved - always start in home directory
            'user_created_files': self.user_created_files,
            'user_created_dirs': self.user_created_dirs,
            'user_modified_files': self.user_modified_files,
            'user_deleted_files': list(self.user_deleted_files),
            'file_permissions': self.file_permissions,
            # Note: current_user is NOT saved - always start as 'pilot'
        }
    
    def _restore_state(self, state):
        """Restore filesystem state from save"""
        # Note: current_path is never restored - always start in home directory
        # Note: current_user is never restored - always start as 'pilot'
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
        self.current_user = "pilot"
    
    def reset_filesystem_keep_user_files(self):
        """
        Reset filesystem to defaults but preserve user-created files.
        Moves all user-created files to the starting directory (blthll).
        """
        # Save user-created files
        saved_files = {}
        saved_dirs = []
        
        # Collect all user-created files
        for path, content in self.user_created_files.items():
            # Extract just the filename
            path_parts = path.strip('/').split('/')
            filename = path_parts[-1]
            # Save to blthll directory
            new_path = '/home/pilot/blthll/' + filename
            saved_files[new_path] = content
        
        # Collect user-created directories (but we'll just keep files for now)
        # Directories are more complex, so we'll skip them for simplicity
        
        # Reset everything
        self.reset_to_defaults()
        
        # Restore user-created files to blthll
        self.user_created_files = saved_files
    
    def _get_default_file_paths(self):
        """
        Build a map of all default files and their paths.
        Returns: dict mapping (normalized content) -> list of paths where that file exists
        """
        file_map = {}
        
        def traverse(node, current_path):
            """Recursively traverse the filesystem tree"""
            if 'files' in node:
                for filename, content in node['files'].items():
                    full_path = current_path + '/' + filename
                    # Normalize content for comparison
                    if isinstance(content, list):
                        content_key = tuple(content)
                    else:
                        content_key = (content,)
                    
                    if content_key not in file_map:
                        file_map[content_key] = []
                    file_map[content_key].append(full_path)
            
            if 'dirs' in node:
                for dirname, subnode in node['dirs'].items():
                    traverse(subnode, current_path + '/' + dirname)
        
        # Traverse from root
        for top_level, node in self.filesystem.items():
            if isinstance(node, dict):
                traverse(node, '/' + top_level)
        
        return file_map
    
    def _get_default_files_in_directory(self, dir_path):
        """
        Get list of default files that should exist in a directory.
        Returns: list of (filename, full_path) tuples
        """
        # Convert path string to path list
        if dir_path.startswith('/'):
            path_parts = [p for p in dir_path.split('/') if p]
        else:
            path_parts = dir_path.split('/')
            path_parts = [p for p in path_parts if p]
        
        # Navigate to directory
        current = self.filesystem
        for part in path_parts:
            if part in current:
                current = current[part]
            elif 'dirs' in current and part in current['dirs']:
                current = current['dirs'][part]
            else:
                return []  # Directory doesn't exist in default filesystem
        
        # Get files from this directory
        files = []
        if 'files' in current:
            for filename in current['files'].keys():
                full_path = '/' + '/'.join(path_parts) + '/' + filename
                files.append((filename, full_path))
        
        return files
    
    def reset_directory(self, dir_path):
        """
        Reset a directory to its default state.
        
        Args:
            dir_path: Directory path (e.g., '/home/pilot/blthll/data' or 'data')
            
        Returns:
            tuple: (success: bool, error_message: str or None)
        """
        # Normalize directory path
        if not dir_path.startswith('/'):
            # Relative path - make it absolute from current directory
            current_pwd = self.get_pwd()
            if dir_path == '.':
                dir_path = current_pwd
            elif dir_path == '..':
                # Parent directory
                if len(self.current_path) > 0:
                    parent_parts = self.current_path[:-1]
                    dir_path = '/' + '/'.join(parent_parts) if parent_parts else '/'
                else:
                    return (False, "Already at root directory")
            else:
                dir_path = current_pwd + '/' + dir_path
        
        # Ensure path ends without trailing slash (except root)
        if dir_path != '/' and dir_path.endswith('/'):
            dir_path = dir_path[:-1]
        
        # Get default files that should be in this directory
        default_files = self._get_default_files_in_directory(dir_path)
        default_file_paths = {full_path for _, full_path in default_files}
        
        # Build map of default file contents to their paths
        default_file_map = self._get_default_file_paths()
        
        # 1. Remove all files in user_created_files in this directory
        # (These are either user-created files or moved default files)
        files_to_remove = []
        for file_path in list(self.user_created_files.keys()):
            if file_path.startswith(dir_path + '/'):
                files_to_remove.append(file_path)
        
        # For moved default files, we need to restore them to their original location
        # by removing them from user_deleted_files at the original path
        for file_path in files_to_remove:
            content = self.user_created_files[file_path]
            if isinstance(content, list):
                content_key = tuple(content)
            else:
                content_key = (content,)
            
            # Check if this is a moved default file
            if content_key in default_file_map:
                # Find the original location(s) of this file
                original_paths = default_file_map[content_key]
                # Remove from user_deleted_files at original locations
                for orig_path in original_paths:
                    if orig_path in self.user_deleted_files:
                        self.user_deleted_files.remove(orig_path)
            
            # Remove from user_created_files
            del self.user_created_files[file_path]
        
        # 3. Restore deleted default files from this directory
        for filename, full_path in default_files:
            if full_path in self.user_deleted_files:
                self.user_deleted_files.remove(full_path)
        
        # 4. Remove user-modified files in this directory (restore to default)
        modified_to_remove = []
        for file_path in list(self.user_modified_files.keys()):
            if file_path.startswith(dir_path + '/'):
                modified_to_remove.append(file_path)
        
        for file_path in modified_to_remove:
            del self.user_modified_files[file_path]
        
        # 5. Remove user-created directories in this directory
        dirs_to_remove = []
        for dir_path_item in self.user_created_dirs:
            if dir_path_item.startswith(dir_path + '/'):
                dirs_to_remove.append(dir_path_item)
        
        for dir_path_item in dirs_to_remove:
            self.user_created_dirs.remove(dir_path_item)
        
        return (True, None)

