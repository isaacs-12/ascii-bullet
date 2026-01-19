"""
Safe Python script execution using RestrictedPython
"""

from RestrictedPython import compile_restricted
from RestrictedPython.Guards import (
    safe_builtins,
    guarded_iter_unpack_sequence,
    safer_getattr,
)
from RestrictedPython.PrintCollector import PrintCollector
import signal
import sys


class ScriptTimeoutError(Exception):
    """Exception raised when script execution times out"""
    pass


class VirtualFile:
    """File-like object that works with the virtual filesystem"""
    
    def __init__(self, filesystem, filename, mode, save_callback=None):
        """
        Initialize virtual file
        
        Args:
            filesystem: VirtualFileSystem instance
            filename: Name of file
            mode: File mode ('r', 'w', 'a', 'x', etc.)
            save_callback: Optional callback to save filesystem after modifications
        """
        self.filesystem = filesystem
        self.filename = filename
        self.mode = mode
        self.save_callback = save_callback
        self.closed = False
        self._position = 0
        self._content = None
        self._modified = False
        
        # Parse mode
        self.readable = 'r' in mode or '+' in mode
        self.writable = 'w' in mode or 'a' in mode or 'x' in mode or '+' in mode
        self.append_mode = 'a' in mode
        self.exclusive = 'x' in mode
        
        # Load existing content if reading or appending
        if self.readable or self.append_mode:
            success, content = self.filesystem.read_file(filename)
            if success:
                self._content = content if isinstance(content, list) else [content]
            else:
                self._content = []
        
        # For write mode, start with empty content
        if 'w' in mode:
            self._content = []
        
        # For append mode, position at end
        if self.append_mode:
            self._position = len(self._content) if self._content else 0
        
        # Check exclusive mode
        if self.exclusive:
            if self.filesystem.file_exists(filename):
                raise FileExistsError(f"[Errno 17] File exists: '{filename}'")
    
    def read(self, size=-1):
        """Read content from file"""
        if not self.readable:
            raise ValueError("File not open for reading")
        if self.closed:
            raise ValueError("I/O operation on closed file")
        
        if self._content is None:
            return ""
        
        # Read from current position
        if size == -1:
            # Read all remaining
            result = '\n'.join(self._content[self._position:])
            self._position = len(self._content)
        else:
            # Read up to size characters (simplified - reads by lines)
            lines = []
            chars_read = 0
            for line in self._content[self._position:]:
                line_with_newline = line + '\n'
                if chars_read + len(line_with_newline) <= size:
                    lines.append(line)
                    chars_read += len(line_with_newline)
                    self._position += 1
                else:
                    break
            result = '\n'.join(lines)
        
        return result
    
    def readline(self):
        """Read a single line"""
        if not self.readable:
            raise ValueError("File not open for reading")
        if self.closed:
            raise ValueError("I/O operation on closed file")
        
        if self._content is None or self._position >= len(self._content):
            return ""
        
        line = self._content[self._position] + '\n'
        self._position += 1
        return line
    
    def readlines(self):
        """Read all lines"""
        if not self.readable:
            raise ValueError("File not open for reading")
        if self.closed:
            raise ValueError("I/O operation on closed file")
        
        if self._content is None:
            return []
        
        lines = [line + '\n' for line in self._content[self._position:]]
        self._position = len(self._content)
        return lines
    
    def write(self, s):
        """Write string to file"""
        if not self.writable:
            raise ValueError("File not open for writing")
        if self.closed:
            raise ValueError("I/O operation on closed file")
        
        if self._content is None:
            self._content = []
        
        # Split by newlines and add lines
        lines = s.split('\n')
        # Remove empty trailing line if string ended with \n
        if lines and lines[-1] == '':
            lines = lines[:-1]
        
        for i, line in enumerate(lines):
            if i == 0 and self.append_mode and self._position < len(self._content):
                # Append to last line in append mode
                self._content[-1] += line
            else:
                if i == 0 and self._position < len(self._content):
                    # Overwrite mode - replace line at position
                    self._content[self._position] = line
                    self._position += 1
                else:
                    # Insert new line
                    if self.append_mode:
                        self._content.append(line)
                    else:
                        if self._position < len(self._content):
                            self._content.insert(self._position, line)
                        else:
                            self._content.append(line)
                        self._position += 1
        
        self._modified = True
        return len(s)
    
    def writelines(self, lines):
        """Write list of lines to file"""
        if not self.writable:
            raise ValueError("File not open for writing")
        if self.closed:
            raise ValueError("I/O operation on closed file")
        
        if self._content is None:
            self._content = []
        
        for line in lines:
            # Remove trailing newline if present (writelines doesn't add them)
            line_clean = line.rstrip('\n')
            if self.append_mode:
                self._content.append(line_clean)
            else:
                if self._position < len(self._content):
                    self._content[self._position] = line_clean
                    self._position += 1
                else:
                    self._content.append(line_clean)
                    self._position += 1
        
        self._modified = True
        return None
    
    def close(self):
        """Close the file and save if modified"""
        if self.closed:
            return
        
        if self._modified and self.writable:
            # Save to filesystem
            if self.filesystem.file_exists(self.filename):
                self.filesystem.write_file(self.filename, self._content, append=False)
            else:
                self.filesystem.create_file(self.filename, self._content)
            
            # Trigger save callback
            if self.save_callback:
                self.save_callback()
        
        self.closed = True
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
        return False  # Don't suppress exceptions
    
    def __iter__(self):
        """Make file iterable"""
        return self
    
    def __next__(self):
        """Next line for iteration"""
        line = self.readline()
        if not line:
            raise StopIteration
        return line


class StatResult:
    """os.stat_result-like object for file statistics"""
    def __init__(self, size, permissions, owner, exists):
        self.st_size = size  # Size in bytes
        self.st_mode = permissions  # Permission string (e.g., 'rwxrwxrwx')
        self.st_uid = owner  # Owner name ('pilot' or 'root')
        self.exists = exists  # Whether file exists
    
    def __repr__(self):
        return f"os.stat_result(st_size={self.st_size}, st_mode='{self.st_mode}', st_uid='{self.st_uid}')"


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


class ScriptTimeoutError(Exception):
    """Raised when script execution times out"""
    pass


class GameScriptAPI:
    """Minimal API wrapper for filesystem access (used internally)"""
    
    def __init__(self, filesystem, output_callback, save_callback=None):
        """
        Initialize the script API
        
        Args:
            filesystem: VirtualFileSystem instance
            output_callback: Function to call with output text
            save_callback: Optional function to call after filesystem modifications
        """
        self.filesystem = filesystem
        self._output = output_callback
        self._save_callback = save_callback


class ScriptExecutor:
    """Executes Python scripts in a restricted environment"""
    
    # Maximum execution time in seconds
    MAX_EXECUTION_TIME = 5
    
    def __init__(self):
        """Initialize the script executor"""
        self.output_lines = []
    
    def _timeout_handler(self, signum, frame):
        """Handle script execution timeout"""
        raise ScriptTimeoutError("Script execution timed out")
        raise ScriptTimeoutError("Script execution timed out (5 second limit)")
    
    def _get_safe_globals(self, game_api):
        """
        Get safe global variables for script execution
        
        Args:
            game_api: GameScriptAPI instance
            
        Returns:
            Dictionary of safe globals
        """
        # Create a safe open() function that uses VirtualFile
        def safe_open(filename, mode='r', buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None):
            """
            Safe open() function that works with virtual filesystem
            
            Args:
                filename: Name of file to open
                mode: File mode ('r', 'w', 'a', 'x', etc.)
                Other args are ignored (for compatibility)
            
            Returns:
                VirtualFile object
            """
            return VirtualFile(
                game_api.filesystem,
                filename,
                mode,
                game_api._save_callback
            )
        
        # Create the VirtualOS instance (which includes path submodule)
        virtual_os = VirtualOS(game_api.filesystem, game_api._save_callback)
        
        # Define a robust custom getattr that explicitly allows our virtual classes
        def custom_getattr(obj, name):
            """
            Allow access to attributes of our specific Virtual classes.
            For everything else, delegate to RestrictedPython's safer_getattr.
            """
            # Allow access to attributes of VirtualOS, VirtualOSPath, VirtualFile, and StatResult
            # We explicitly check the type to prevent access to unauthorized objects
            if isinstance(obj, (VirtualOS, VirtualOSPath, VirtualFile, StatResult)):
                return getattr(obj, name)
                
            return safer_getattr(obj, name)
        
        # Construct the safe globals first
        safe_globals = {
            '__builtins__': {
                # Use safe_builtins as base and extend it
                **safe_builtins,
                
                # Safe file I/O
                'open': safe_open,
                
                # Exception types
                'FileNotFoundError': FileNotFoundError,
                'FileExistsError': FileExistsError,
                'OSError': OSError,
                'PermissionError': PermissionError,
                'ValueError': ValueError,
                'TypeError': TypeError,
            },
            
            # The Magic Sauce: Inject our custom attribute guard
            '_getattr_': custom_getattr,
            
            # Standard RP guards
            '_iter_unpack_sequence_': guarded_iter_unpack_sequence,
            '_getiter_': iter,
            '_print_': PrintCollector,  # Helper for print statements
            
            # Expose our VirtualOS instance as 'os'
            'os': virtual_os,
        }
        
        # Create a safe __import__ that handles both 'os' and 'os.path'
        # When Python does 'import os.path', it calls __import__('os.path', ...)
        # We need to return the os module, and Python will then access .path from it
        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            """Safe import that only allows importing modules from safe_globals"""
            # Handle 'os' module (including 'import os.path' which first imports 'os')
            if name == 'os' or name == 'os.path':
                return safe_globals['os']
            # Check if it's in our safe globals
            if name in safe_globals:
                return safe_globals[name]
            raise ImportError(f"No module named '{name}'")
        
        # Add safe __import__ to builtins
        safe_globals['__builtins__']['__import__'] = safe_import
        
        return safe_globals
    
    def execute(self, code, filesystem, output_callback, save_callback=None):
        """
        Execute Python code in a restricted environment
        
        Args:
            code: Python code string or list of lines
            filesystem: VirtualFileSystem instance
            output_callback: Function to call with each output line
            save_callback: Optional function to call after filesystem modifications
            
        Returns:
            tuple: (success: bool, error_message: str or None)
        """
        # Convert list to string if needed
        if isinstance(code, list):
            code = '\n'.join(code)
        
        # Create game API
        game_api = GameScriptAPI(filesystem, output_callback, save_callback)
        
        # Compile code with restrictions
        try:
            compile_result = compile_restricted(
                code,
                filename='<string>',
                mode='exec'
            )
            
            # Check for compilation errors (RestrictedPython 8.x returns CompileResult)
            if hasattr(compile_result, 'errors') and compile_result.errors:
                error_msg = '\n'.join(compile_result.errors)
                return (False, f"Compilation error:\n{error_msg}")
            
            # Get the code object
            if hasattr(compile_result, 'code'):
                byte_code = compile_result.code
            else:
                byte_code = compile_result
                
        except SyntaxError as e:
            return (False, f"Syntax error: {e}")
        except Exception as e:
            return (False, f"Compilation Error: {e}")
        
        # Prepare execution environment
        safe_globals = self._get_safe_globals(game_api)
        safe_locals = {}
        
        # Set up timeout (only on Unix-like systems)
        if hasattr(signal, 'SIGALRM'):
            old_handler = signal.signal(signal.SIGALRM, self._timeout_handler)
            signal.alarm(self.MAX_EXECUTION_TIME)
        
        try:
            # Execute the code
            exec(byte_code, safe_globals, safe_locals)
            
            # Retrieve printed text
            # RestrictedPython accumulates print output in a local variable usually named '_print'
            # which is an instance of PrintCollector.
            print_collector = safe_locals.get('_print')
            if print_collector:
                output = print_collector()  # Calling it retrieves the string
                if output:
                    for line in output.strip().split('\n'):
                        if line.strip():  # Only process non-empty lines
                            output_callback(line)
            
            return (True, None)
            
        except ScriptTimeoutError as e:
            return (False, str(e))
        except SystemExit:
            return (False, "Script attempted to exit")
        except Exception as e:
            # Helpful for debugging: print the traceback if needed,
            # but for users just return the error
            error_type = type(e).__name__
            error_msg = str(e)
            return (False, f"Runtime error: {error_type}: {error_msg}")
        finally:
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

