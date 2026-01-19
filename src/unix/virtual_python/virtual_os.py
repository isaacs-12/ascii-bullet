"""
Virtual os module implementation for restricted Python execution
"""


class StatResult:
    """os.stat_result-like object for file statistics"""
    def __init__(self, size, permissions, owner, exists):
        self.st_size = size  # Size in bytes
        self.st_mode = permissions  # Permission string (e.g., 'rwxrwxrwx')
        self.st_uid = owner  # Owner name ('pilot' or 'root')
        self.exists = exists  # Whether file exists
    
    def __repr__(self):
        return f"os.stat_result(st_size={self.st_size}, st_mode='{self.st_mode}', st_uid='{self.st_uid}')"


class VirtualOSPath:
    """Simulated os.path module for the virtual filesystem"""
    
    def __init__(self, filesystem):
        self.filesystem = filesystem
    
    def exists(self, path):
        """Check if path exists"""
        return self.filesystem.file_exists(path)
    
    def getsize(self, path):
        """Get file size in bytes"""
        if not self.filesystem.file_exists(path):
            raise FileNotFoundError(f"[Errno 2] No such file or directory: '{path}'")
        # Calculate size
        success, content = self.filesystem.read_file(path)
        if not success:
            return 0
        elif isinstance(content, list):
            return sum(len(line) + 1 for line in content)
        else:
            return len(content)
    
    def isfile(self, path):
        """Check if path is a file (not a directory)"""
        if not self.filesystem.file_exists(path):
            return False
        # In our filesystem, directories end with '/'
        contents = self.filesystem.list_directory()
        return path in contents and not path.endswith('/')
    
    def isdir(self, path):
        """Check if path is a directory"""
        # In our filesystem, directories end with '/'
        # Check if the path (with or without trailing slash) exists as a directory
        if path.endswith('/'):
            dir_path = path
        else:
            dir_path = path + '/'
        
        contents = self.filesystem.list_directory()
        return dir_path in contents


class VirtualOS:
    """Simulated os module for the virtual filesystem"""
    
    def __init__(self, filesystem, save_callback=None):
        self.filesystem = filesystem
        self._save_callback = save_callback
        
        # Initialize os.path submodule
        self.path = VirtualOSPath(filesystem)
        
        # OS Constants
        self.F_OK = 0
        self.R_OK = 4
        self.W_OK = 2
        self.X_OK = 1
        self.name = 'posix'
        self.sep = '/'
        self.linesep = '\n'
    
    def getcwd(self):
        """Get current working directory"""
        return self.filesystem.get_pwd()
    
    def listdir(self, path=None):
        """List directory contents"""
        if path is None:
            return self.filesystem.list_directory()
        # For now, only support current directory
        # Could extend to support path parameter
        return self.filesystem.list_directory()
    
    def stat(self, path):
        """Get file statistics"""
        if not self.filesystem.file_exists(path):
            raise FileNotFoundError(f"[Errno 2] No such file or directory: '{path}'")
        
        # Calculate size
        success, content = self.filesystem.read_file(path)
        if not success:
            size = 0
        elif isinstance(content, list):
            size = sum(len(line) + 1 for line in content)
        else:
            size = len(content)
        
        permissions = self.filesystem.get_permissions(path)
        owner = self.filesystem.get_file_owner(path)
        
        return StatResult(size, permissions, owner, True)
    
    def access(self, path, mode):
        """
        Check file access permissions
        
        Args:
            path: File path
            mode: Access mode (os.F_OK, os.R_OK, os.W_OK, os.X_OK)
        """
        if not self.filesystem.file_exists(path):
            return False
        
        # Map mode constants to permission checks
        if mode == 0:  # F_OK - existence
            return True
        elif mode == 4:  # R_OK - read
            return self.filesystem.check_permission(path, 'r')
        elif mode == 2:  # W_OK - write
            return self.filesystem.check_permission(path, 'w')
        elif mode == 1:  # X_OK - execute
            return self.filesystem.check_permission(path, 'x')
        else:
            # Multiple modes (bitwise OR)
            result = True
            if mode & 4:  # R_OK
                result = result and self.filesystem.check_permission(path, 'r')
            if mode & 2:  # W_OK
                result = result and self.filesystem.check_permission(path, 'w')
            if mode & 1:  # X_OK
                result = result and self.filesystem.check_permission(path, 'x')
            return result
    
    def remove(self, path):
        """Remove (delete) a file"""
        # Check if file exists first
        if not self.filesystem.file_exists(path):
            raise FileNotFoundError(f"[Errno 2] No such file or directory: '{path}'")
        # Then try to delete
        success, error = self.filesystem.delete_file(path)
        if not success:
            raise OSError(error)
        if self._save_callback:
            self._save_callback()
    
    def unlink(self, path):
        """Alias for remove()"""
        self.remove(path)
