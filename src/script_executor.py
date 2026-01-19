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
from io import StringIO


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


class ScriptTimeoutError(Exception):
    """Raised when script execution times out"""
    pass


class GameScriptAPI:
    """Safe API that scripts can use to interact with the game"""
    
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
    
    def read_file(self, filename):
        """
        Read a file from the virtual filesystem
        
        Args:
            filename: Name of file to read
            
        Returns:
            List of lines if successful, None if not found
        """
        success, content = self.filesystem.read_file(filename)
        if success:
            return content
        return None
    
    def list_files(self):
        """
        List files in current directory
        
        Returns:
            List of filenames and directories
        """
        return self.filesystem.list_directory()
    
    def get_pwd(self):
        """Get current working directory"""
        return self.filesystem.get_pwd()
    
    def file_exists(self, filename):
        """Check if a file exists"""
        return self.filesystem.file_exists(filename)
    
    def get_file_size(self, filename):
        """
        Get the size of a file in bytes
        
        Args:
            filename: Name of file
            
        Returns:
            int: File size in bytes, or None if file doesn't exist
        """
        success, content = self.filesystem.read_file(filename)
        if not success:
            return None
        
        # Calculate size: sum of line lengths + newlines
        if isinstance(content, list):
            # Each line + newline character
            return sum(len(line) + 1 for line in content)
        else:
            return len(content)
    
    def stat(self, filename):
        """
        Get file statistics/metadata
        
        Args:
            filename: Name of file
            
        Returns:
            dict with keys: size, permissions, owner, exists
            Returns None if file doesn't exist
        """
        if not self.filesystem.file_exists(filename):
            return None
        
        size = self.get_file_size(filename)
        permissions = self.filesystem.get_permissions(filename)
        owner = self.filesystem.get_file_owner(filename)
        
        return {
            'size': size,  # Size in bytes
            'size_bits': size * 8,  # Size in bits
            'permissions': permissions,
            'owner': owner,
            'exists': True
        }
    
    def get_permissions(self, filename):
        """
        Get file permissions string
        
        Args:
            filename: Name of file
            
        Returns:
            str: Permission string (e.g., "rwx" or "rwxrwxrwx"), or None if not found
        """
        if not self.filesystem.file_exists(filename):
            return None
        return self.filesystem.get_permissions(filename)
    
    def get_owner(self, filename):
        """
        Get file owner
        
        Args:
            filename: Name of file
            
        Returns:
            str: Owner name ("pilot" or "root"), or None if not found
        """
        if not self.filesystem.file_exists(filename):
            return None
        return self.filesystem.get_file_owner(filename)
    
    def create_file(self, filename, content=""):
        """
        Create a new file in the current directory
        
        Args:
            filename: Name of file to create
            content: Initial content (string or list of strings)
            
        Returns:
            tuple: (success: bool, error_message: str or None)
            If success is True, error_message is None
            If success is False, error_message contains the error
        """
        success, error = self.filesystem.create_file(filename, content)
        if success and self._save_callback:
            self._save_callback()
        return (success, error)
    
    def write_file(self, filename, content, append=False):
        """
        Write content to a file (overwrites or appends)
        
        Args:
            filename: Name of file
            content: Content to write (string or list of strings)
            append: If True, append instead of overwrite (default False)
            
        Returns:
            tuple: (success: bool, error_message: str or None)
            If success is True, error_message is None
            If success is False, error_message contains the error
        """
        success, error = self.filesystem.write_file(filename, content, append=append)
        if success and self._save_callback:
            self._save_callback()
        return (success, error)
    
    def delete_file(self, filename):
        """
        Delete a file from the current directory
        
        Args:
            filename: Name of file to delete
            
        Returns:
            tuple: (success: bool, error_message: str or None)
            If success is True, error_message is None
            If success is False, error_message contains the error
        """
        success, error = self.filesystem.delete_file(filename)
        if success and self._save_callback:
            self._save_callback()
        return (success, error)


class ScriptExecutor:
    """Executes Python scripts in a restricted environment"""
    
    # Maximum execution time in seconds
    MAX_EXECUTION_TIME = 5
    
    def __init__(self):
        """Initialize the script executor"""
        self.output_lines = []
    
    def _timeout_handler(self, signum, frame):
        """Handle script execution timeout"""
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
        
        # Start with safe builtins
        safe_globals = {
            '__builtins__': {
                # Type constructors
                'int': int,
                'float': float,
                'str': str,
                'bool': bool,
                'list': list,
                'dict': dict,
                'tuple': tuple,
                'set': set,
                
                # Common functions
                'len': len,
                'range': range,
                'enumerate': enumerate,
                'zip': zip,
                'map': map,
                'filter': filter,
                'sorted': sorted,
                'sum': sum,
                'min': min,
                'max': max,
                'abs': abs,
                'round': round,
                
                # String methods
                'chr': chr,
                'ord': ord,
                
                # Other safe operations
                'reversed': reversed,
                'any': any,
                'all': all,
                
                # PrintCollector for print() support
                '_print_': PrintCollector,
                '_getiter_': guarded_iter_unpack_sequence,
                
                # Safe file I/O
                'open': safe_open,
                
                # Prevent access to dangerous builtins
                '__import__': None,
                'exec': None,
                'eval': None,
                'compile': None,
                '__builtins__': None,
            },
            
            # Required guards for RestrictedPython
            '_getattr_': safer_getattr,
            '_iter_unpack_sequence_': guarded_iter_unpack_sequence,
            '_getiter_': iter,  # Use built-in iter
            
            # Game API
            'game': game_api,
        }
        
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
        
        # Prepare execution environment
        safe_globals = self._get_safe_globals(game_api)
        safe_locals = {}
        
        # Set up timeout (only on Unix-like systems)
        if hasattr(signal, 'SIGALRM'):
            old_handler = signal.signal(signal.SIGALRM, self._timeout_handler)
            signal.alarm(self.MAX_EXECUTION_TIME)
        
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        try:
            # Execute the compiled code
            exec(byte_code, safe_globals, safe_locals)
            
            # Get printed output from PrintCollector
            if '_print' in safe_locals:
                print_collector = safe_locals['_print']
                if hasattr(print_collector, '__call__'):
                    # Get the printed text
                    printed_text = print_collector()
                    if printed_text:
                        for line in printed_text.rstrip('\n').split('\n'):
                            output_callback(line)
            
            # Also capture stdout (fallback)
            printed_output = sys.stdout.getvalue()
            if printed_output:
                for line in printed_output.rstrip('\n').split('\n'):
                    output_callback(line)
            
            return (True, None)
            
        except ScriptTimeoutError as e:
            return (False, str(e))
        
        except Exception as e:
            # Catch any runtime errors
            return (False, f"Runtime error: {type(e).__name__}: {e}")
        
        finally:
            # Restore stdout
            sys.stdout = old_stdout
            
            # Cancel timeout
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

