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


class ScriptTimeoutError(Exception):
    """Raised when script execution times out"""
    pass


class GameScriptAPI:
    """Safe API that scripts can use to interact with the game"""
    
    def __init__(self, filesystem, output_callback):
        """
        Initialize the script API
        
        Args:
            filesystem: VirtualFileSystem instance
            output_callback: Function to call with output text
        """
        self.filesystem = filesystem
        self._output = output_callback
    
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
                
                # Prevent access to dangerous builtins
                '__import__': None,
                'open': None,
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
    
    def execute(self, code, filesystem, output_callback):
        """
        Execute Python code in a restricted environment
        
        Args:
            code: Python code string or list of lines
            filesystem: VirtualFileSystem instance
            output_callback: Function to call with each output line
            
        Returns:
            tuple: (success: bool, error_message: str or None)
        """
        # Convert list to string if needed
        if isinstance(code, list):
            code = '\n'.join(code)
        
        # Create game API
        game_api = GameScriptAPI(filesystem, output_callback)
        
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

