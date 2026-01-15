"""
Simple modal text editor for the terminal
"""

import pygame


class TextEditor:
    """A simple vim-style text editor"""
    
    MODE_NORMAL = 0
    MODE_INSERT = 1
    MODE_COMMAND = 2
    
    def __init__(self, filename, initial_content=None):
        """
        Initialize the text editor
        
        Args:
            filename: Name of file being edited
            initial_content: List of lines (or None for new file)
        """
        self.filename = filename
        self.lines = initial_content[:] if initial_content else [""]
        self.cursor_line = 0
        self.cursor_col = 0
        self.mode = self.MODE_NORMAL
        self.command_buffer = ""
        self.message = f"Editing: {filename}  (Press 'i' to insert, ':' for commands)"
        self.modified = False
        self.should_exit = False
        self.should_save = False
    
    def handle_event(self, event):
        """
        Handle a keyboard event
        
        Args:
            event: pygame keyboard event
            
        Returns:
            bool: True if event was handled
        """
        if event.type != pygame.KEYDOWN:
            return False
        
        if self.mode == self.MODE_NORMAL:
            return self._handle_normal_mode(event)
        elif self.mode == self.MODE_INSERT:
            return self._handle_insert_mode(event)
        elif self.mode == self.MODE_COMMAND:
            return self._handle_command_mode(event)
        
        return False
    
    def _handle_normal_mode(self, event):
        """Handle events in normal mode"""
        if event.key == pygame.K_i:
            # Enter insert mode
            self.mode = self.MODE_INSERT
            self.message = "-- INSERT --"
            return True
        
        elif event.key == pygame.K_COLON or (event.unicode == ':'):
            # Enter command mode
            self.mode = self.MODE_COMMAND
            self.command_buffer = ""
            self.message = ":"
            return True
        
        elif event.key == pygame.K_h or event.key == pygame.K_LEFT:
            # Move cursor left
            self.cursor_col = max(0, self.cursor_col - 1)
            return True
        
        elif event.key == pygame.K_j or event.key == pygame.K_DOWN:
            # Move cursor down
            self.cursor_line = min(len(self.lines) - 1, self.cursor_line + 1)
            self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_line]))
            return True
        
        elif event.key == pygame.K_k or event.key == pygame.K_UP:
            # Move cursor up
            self.cursor_line = max(0, self.cursor_line - 1)
            self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_line]))
            return True
        
        elif event.key == pygame.K_l or event.key == pygame.K_RIGHT:
            # Move cursor right
            self.cursor_col = min(len(self.lines[self.cursor_line]), self.cursor_col + 1)
            return True
        
        elif event.key == pygame.K_o:
            # Insert new line below and enter insert mode
            self.cursor_line += 1
            self.lines.insert(self.cursor_line, "")
            self.cursor_col = 0
            self.mode = self.MODE_INSERT
            self.message = "-- INSERT --"
            self.modified = True
            return True
        
        elif event.key == pygame.K_a:
            # Enter insert mode after cursor
            self.cursor_col = min(len(self.lines[self.cursor_line]), self.cursor_col + 1)
            self.mode = self.MODE_INSERT
            self.message = "-- INSERT --"
            return True
        
        return False
    
    def _handle_insert_mode(self, event):
        """Handle events in insert mode"""
        if event.key == pygame.K_ESCAPE:
            # Return to normal mode
            self.mode = self.MODE_NORMAL
            self.message = f"Editing: {self.filename}  (Press 'i' to insert, ':' for commands)"
            return True
        
        elif event.key == pygame.K_RETURN:
            # Insert new line
            current_line = self.lines[self.cursor_line]
            self.lines[self.cursor_line] = current_line[:self.cursor_col]
            self.lines.insert(self.cursor_line + 1, current_line[self.cursor_col:])
            self.cursor_line += 1
            self.cursor_col = 0
            self.modified = True
            return True
        
        elif event.key == pygame.K_BACKSPACE:
            # Delete character before cursor
            if self.cursor_col > 0:
                line = self.lines[self.cursor_line]
                self.lines[self.cursor_line] = line[:self.cursor_col-1] + line[self.cursor_col:]
                self.cursor_col -= 1
                self.modified = True
            elif self.cursor_line > 0:
                # Join with previous line
                prev_line = self.lines[self.cursor_line - 1]
                self.cursor_col = len(prev_line)
                self.lines[self.cursor_line - 1] = prev_line + self.lines[self.cursor_line]
                del self.lines[self.cursor_line]
                self.cursor_line -= 1
                self.modified = True
            return True
        
        elif event.unicode and event.unicode.isprintable():
            # Insert character
            line = self.lines[self.cursor_line]
            self.lines[self.cursor_line] = line[:self.cursor_col] + event.unicode + line[self.cursor_col:]
            self.cursor_col += 1
            self.modified = True
            return True
        
        return False
    
    def _handle_command_mode(self, event):
        """Handle events in command mode"""
        if event.key == pygame.K_ESCAPE:
            # Cancel command
            self.mode = self.MODE_NORMAL
            self.message = f"Editing: {self.filename}  (Press 'i' to insert, ':' for commands)"
            return True
        
        elif event.key == pygame.K_RETURN:
            # Execute command
            self._execute_command(self.command_buffer)
            return True
        
        elif event.key == pygame.K_BACKSPACE:
            # Delete from command buffer
            if self.command_buffer:
                self.command_buffer = self.command_buffer[:-1]
                self.message = ":" + self.command_buffer
            else:
                # Exit command mode if buffer is empty
                self.mode = self.MODE_NORMAL
                self.message = f"Editing: {self.filename}  (Press 'i' to insert, ':' for commands)"
            return True
        
        elif event.unicode and event.unicode.isprintable():
            # Add to command buffer
            self.command_buffer += event.unicode
            self.message = ":" + self.command_buffer
            return True
        
        return False
    
    def _execute_command(self, command):
        """Execute a command mode command"""
        cmd = command.strip().lower()
        
        if cmd in ['w', 'write']:
            # Write (save) file
            self.should_save = True
            self.modified = False
            self.mode = self.MODE_NORMAL
            self.message = f'"{self.filename}" written'
        
        elif cmd in ['q', 'quit']:
            # Quit
            if self.modified:
                self.message = "No write since last change (use :q! to force)"
                self.mode = self.MODE_NORMAL
            else:
                self.should_exit = True
        
        elif cmd in ['q!', 'quit!']:
            # Force quit
            self.should_exit = True
        
        elif cmd in ['wq', 'x']:
            # Write and quit
            self.should_save = True
            self.should_exit = True
            self.modified = False
        
        else:
            self.message = f"Unknown command: {command}"
            self.mode = self.MODE_NORMAL
    
    def get_display_lines(self, max_lines=30):
        """
        Get lines to display in the terminal
        
        Args:
            max_lines: Maximum number of lines to show
            
        Returns:
            list: Lines to display with line numbers
        """
        display = []
        
        # Calculate visible range (show cursor in middle if possible)
        start_line = max(0, self.cursor_line - max_lines // 2)
        end_line = min(len(self.lines), start_line + max_lines - 1)  # -1 for status line
        
        for i in range(start_line, end_line):
            line_num = f"{i+1:3} "
            cursor_marker = ""
            
            # Show cursor on current line
            if i == self.cursor_line and self.mode != self.MODE_COMMAND:
                line_content = self.lines[i]
                cursor_pos = self.cursor_col
                # Insert cursor marker
                if cursor_pos <= len(line_content):
                    cursor_marker = line_content[:cursor_pos] + "█" + line_content[cursor_pos:]
                else:
                    cursor_marker = line_content + "█"
                display.append(line_num + cursor_marker)
            else:
                display.append(line_num + self.lines[i])
        
        # Add empty lines if needed
        while len(display) < max_lines - 1:
            display.append("~")
        
        # Add status line
        display.append(self.message)
        
        return display
    
    def get_content(self):
        """Get the edited content"""
        return self.lines[:]

