"""
Virtual file implementation for restricted Python execution
"""


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
        # Skip empty string from trailing newline (last element if string ended with \n)
        for i, line in enumerate(lines):
            if i == len(lines) - 1 and line == '':
                continue
            
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
