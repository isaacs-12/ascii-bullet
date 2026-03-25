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

from src.unix.virtual_python.virtual_file import VirtualFile
from src.unix.virtual_python.virtual_os import VirtualOS, VirtualOSPath, StatResult


class ScriptTimeoutError(Exception):
    """Exception raised when script execution times out"""
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
                    for line in output.rstrip('\n').split('\n'):
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
