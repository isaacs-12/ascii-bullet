"""
Simple text editor state for editing files in the virtual filesystem
"""

import pygame
from src.states.base_state import BaseState


class EditorState(BaseState):
    """A basic text editor for the virtual filesystem"""
    
    def __init__(self, game, filesystem, filename, previous_state, editor_name="vim"):
        """
        Initialize the editor
        
        Args:
            game: Game instance
            filesystem: VirtualFileSystem instance
            filename: Name of file to edit
            previous_state: State to return to when done
            editor_name: Name of the editor ("vim" or "emacs")
        """
        super().__init__(game)
        self.filesystem = filesystem
        self.filename = filename
        self.previous_state = previous_state
        self.editor_name = editor_name
        
        # Editor state
        self.lines = []
        self.current_line = 0
        self.cursor_pos = 0
        # Emacs is always in "edit" mode, vim has modal editing
        if editor_name == "emacs":
            self.mode = "edit"
        else:
            self.mode = "normal"  # "normal", "insert", or "command"
        self.command_buffer = ""
        self.message = ""
        self.is_modified = False
        self.is_readonly = False  # Set to True if file can't be read due to permissions
        self.ctrl_x_pressed = False  # For emacs C-x prefix
        
        # Load file if it exists
        success, content = filesystem.read_file(filename)
        if success:
            if isinstance(content, list):
                self.lines = [str(line) for line in content]
            else:
                self.lines = [str(content)]
            self.is_readonly = False
        else:
            # Check if it's a permission error or just a new file
            if "Permission denied" in content:
                # Permission denied - show error in the file
                self.lines = [
                    "=" * 60,
                    "ERROR: Permission Denied",
                    "=" * 60,
                    "",
                    f"You do not have permission to read this file: {filename}",
                    "",
                    "This file may be owned by another user (e.g., root).",
                    "You may need to use 'sudo' or change file permissions with 'chmod'.",
                    "",
                    "Press :q to quit without making changes.",
                    ""
                ]
                self.is_readonly = True
            else:
                # New file
                self.lines = [""]
                self.is_readonly = False
        
        # Ensure at least one line
        if not self.lines:
            self.lines = [""]
    
    def enter(self):
        """Called when entering this state"""
        if self.is_readonly:
            self.message = f"PERMISSION DENIED: {self.filename} (read-only) | :q to quit"
        elif self.editor_name == "emacs":
            self.message = f"GNU Emacs: {self.filename} | C-x C-s=save, C-x C-c=quit"
        else:
            self.message = f"Editing: {self.filename} | ESC=normal, i=insert, :w=save, :q=quit, :wq=save&quit"
    
    def exit(self):
        """Called when exiting this state"""
        pass
    
    def handle_events(self, events):
        """Handle input events"""
        for event in events:
            if event.type == pygame.KEYDOWN:
                if self.editor_name == "emacs":
                    self._handle_emacs_mode(event)
                elif self.mode == "normal":
                    self._handle_normal_mode(event)
                elif self.mode == "insert":
                    self._handle_insert_mode(event)
                elif self.mode == "command":
                    self._handle_command_mode(event)
    
    def _handle_emacs_mode(self, event):
        """Handle keys in emacs mode (always editing)"""
        # Check if file is readonly (except for quit commands)
        if self.is_readonly:
            # Only allow C-x C-c to quit
            if self.ctrl_x_pressed:
                if event.mod & pygame.KMOD_CTRL and event.key == pygame.K_c:
                    self.game.change_state(self.previous_state, call_enter=False)
                self.ctrl_x_pressed = False
                return
            elif event.mod & pygame.KMOD_CTRL and event.key == pygame.K_x:
                self.ctrl_x_pressed = True
                return
            # All other keys blocked
            if event.unicode and event.unicode.isprintable():
                self.message = "Error: File is read-only (permission denied)"
            return
        
        # If we're waiting for the second key in C-x sequence
        if self.ctrl_x_pressed:
            # Check if this is a Ctrl combination
            if event.mod & pygame.KMOD_CTRL:
                if event.key == pygame.K_s:
                    # C-x C-s: Save
                    self.ctrl_x_pressed = False
                    self._save_file()
                    return
                elif event.key == pygame.K_c:
                    # C-x C-c: Quit
                    self.ctrl_x_pressed = False
                    if self.is_modified:
                        self.message = "Modified buffer! Save with C-x C-s first"
                    else:
                        self.game.change_state(self.previous_state, call_enter=False)
                    return
                elif event.key == pygame.K_x:
                    # C-x C-x: Cancel the sequence and start a new one (or just cancel)
                    self.ctrl_x_pressed = False
                    self.message = f"GNU Emacs: {self.filename} | C-x C-s=save, C-x C-c=quit"
                    return
                else:
                    # Some other Ctrl key - cancel the sequence
                    self.ctrl_x_pressed = False
                    self.message = f"GNU Emacs: {self.filename} | C-x C-s=save, C-x C-c=quit"
                    # Continue processing the key normally
            else:
                # Not a Ctrl key - cancel the C-x sequence
                self.ctrl_x_pressed = False
                self.message = f"GNU Emacs: {self.filename} | C-x C-s=save, C-x C-c=quit"
                # Continue processing the key normally
        
        # Check for Ctrl key combinations (only if not in a C-x sequence)
        if not self.ctrl_x_pressed and event.mod & pygame.KMOD_CTRL:
            if event.key == pygame.K_x:
                # C-x prefix - wait for next key
                self.ctrl_x_pressed = True
                self.message = "C-x-"
                return
        
        # Regular editing (same as vim insert mode)
        if event.key == pygame.K_RETURN:
            # Insert new line
            current = self.lines[self.current_line]
            self.lines[self.current_line] = current[:self.cursor_pos]
            self.lines.insert(self.current_line + 1, current[self.cursor_pos:])
            self.current_line += 1
            self.cursor_pos = 0
            self.is_modified = True
        
        elif event.key == pygame.K_BACKSPACE:
            # Delete character
            if self.cursor_pos > 0:
                line = self.lines[self.current_line]
                self.lines[self.current_line] = line[:self.cursor_pos-1] + line[self.cursor_pos:]
                self.cursor_pos -= 1
                self.is_modified = True
            elif self.current_line > 0:
                # Join with previous line
                prev_line = self.lines[self.current_line - 1]
                current_line = self.lines[self.current_line]
                self.lines[self.current_line - 1] = prev_line + current_line
                del self.lines[self.current_line]
                self.current_line -= 1
                self.cursor_pos = len(prev_line)
                self.is_modified = True
        
        elif event.key == pygame.K_UP:
            if self.current_line > 0:
                self.current_line -= 1
                self.cursor_pos = min(self.cursor_pos, len(self.lines[self.current_line]))
        
        elif event.key == pygame.K_DOWN:
            if self.current_line < len(self.lines) - 1:
                self.current_line += 1
                self.cursor_pos = min(self.cursor_pos, len(self.lines[self.current_line]))
        
        elif event.key == pygame.K_LEFT:
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
        
        elif event.key == pygame.K_RIGHT:
            if self.cursor_pos < len(self.lines[self.current_line]):
                self.cursor_pos += 1
        
        elif event.unicode and event.unicode.isprintable():
            # Insert character
            line = self.lines[self.current_line]
            self.lines[self.current_line] = line[:self.cursor_pos] + event.unicode + line[self.cursor_pos:]
            self.cursor_pos += 1
            self.is_modified = True
    
    def _handle_normal_mode(self, event):
        """Handle keys in normal mode"""
        if event.key == pygame.K_ESCAPE:
            # ESC in normal mode does nothing (already in normal mode)
            # Just update the message to show we're in normal mode
            self.message = f"Editing: {self.filename} | ESC=normal, i=insert, :w=save, :q=quit, :wq=save&quit"
        
        elif event.key == pygame.K_i:
            # Enter insert mode (only if not readonly)
            if self.is_readonly:
                self.message = "Error: File is read-only (permission denied)"
            else:
                self.mode = "insert"
                self.message = "-- INSERT MODE -- (ESC to return to normal mode)"
        
        elif event.key == pygame.K_UP:
            # Move up
            if self.current_line > 0:
                self.current_line -= 1
                self.cursor_pos = min(self.cursor_pos, len(self.lines[self.current_line]))
        
        elif event.key == pygame.K_DOWN:
            # Move down
            if self.current_line < len(self.lines) - 1:
                self.current_line += 1
                self.cursor_pos = min(self.cursor_pos, len(self.lines[self.current_line]))
        
        elif event.key == pygame.K_LEFT:
            # Move left
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
        
        elif event.key == pygame.K_RIGHT:
            # Move right
            if self.cursor_pos < len(self.lines[self.current_line]):
                self.cursor_pos += 1
        
        elif event.unicode == ':':
            # Start command mode
            self.mode = "command"
            self.command_buffer = ":"
            self.message = ":"
            
    def _handle_command_mode(self, event):
        """Handle command input (called when mode == "command")"""
        if event.key == pygame.K_RETURN:
            # Execute command
            cmd = self.command_buffer[1:]  # Remove ':'
            self._execute_command(cmd)
            self.mode = "normal"
        
        elif event.key == pygame.K_ESCAPE:
            # Cancel command
            self.mode = "normal"
            self.message = f"Editing: {self.filename}"
        
        elif event.key == pygame.K_BACKSPACE:
            if len(self.command_buffer) > 1:
                self.command_buffer = self.command_buffer[:-1]
                self.message = self.command_buffer
        
        elif event.unicode and event.unicode.isprintable():
            self.command_buffer += event.unicode
            self.message = self.command_buffer
    
    def _handle_insert_mode(self, event):
        """Handle keys in insert mode"""
        if event.key == pygame.K_ESCAPE:
            # Return to normal mode
            self.mode = "normal"
            self.message = f"Editing: {self.filename} | ESC=normal, i=insert, :w=save, :q=quit, :wq=save&quit"
        
        elif event.key == pygame.K_RETURN:
            # Insert new line
            current = self.lines[self.current_line]
            self.lines[self.current_line] = current[:self.cursor_pos]
            self.lines.insert(self.current_line + 1, current[self.cursor_pos:])
            self.current_line += 1
            self.cursor_pos = 0
            self.is_modified = True
        
        elif event.key == pygame.K_BACKSPACE:
            # Delete character
            if self.cursor_pos > 0:
                line = self.lines[self.current_line]
                self.lines[self.current_line] = line[:self.cursor_pos-1] + line[self.cursor_pos:]
                self.cursor_pos -= 1
                self.is_modified = True
            elif self.current_line > 0:
                # Join with previous line
                prev_line = self.lines[self.current_line - 1]
                current_line = self.lines[self.current_line]
                self.lines[self.current_line - 1] = prev_line + current_line
                del self.lines[self.current_line]
                self.current_line -= 1
                self.cursor_pos = len(prev_line)
                self.is_modified = True
        
        elif event.key == pygame.K_UP:
            # Move up in insert mode
            if self.current_line > 0:
                self.current_line -= 1
                self.cursor_pos = min(self.cursor_pos, len(self.lines[self.current_line]))
        
        elif event.key == pygame.K_DOWN:
            # Move down in insert mode
            if self.current_line < len(self.lines) - 1:
                self.current_line += 1
                self.cursor_pos = min(self.cursor_pos, len(self.lines[self.current_line]))
        
        elif event.key == pygame.K_LEFT:
            # Move left in insert mode
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
        
        elif event.key == pygame.K_RIGHT:
            # Move right in insert mode
            if self.cursor_pos < len(self.lines[self.current_line]):
                self.cursor_pos += 1
        
        elif event.unicode and event.unicode.isprintable():
            # Insert character
            line = self.lines[self.current_line]
            self.lines[self.current_line] = line[:self.cursor_pos] + event.unicode + line[self.cursor_pos:]
            self.cursor_pos += 1
            self.is_modified = True
    
    def _execute_command(self, cmd):
        """Execute editor command"""
        if cmd == 'w':
            # Save file
            self._save_file()
        
        elif cmd == 'q':
            # Quit
            if self.is_modified:
                self.message = "Warning: Unsaved changes! Use :wq to save or :q! to force quit"
            else:
                self.game.change_state(self.previous_state, call_enter=False)
        
        elif cmd == 'q!':
            # Force quit without saving
            self.game.change_state(self.previous_state, call_enter=False)
        
        elif cmd == 'wq':
            # Save and quit
            if self._save_file():
                self.game.change_state(self.previous_state, call_enter=False)
        
        else:
            self.message = f"Unknown command: :{cmd}"
    
    def _save_file(self):
        """Save the file"""
        # Check if file is readonly
        if self.is_readonly:
            self.message = "Error: Cannot save - file is read-only (permission denied)"
            return False
        
        try:
            full_path = self.filesystem.get_pwd() + '/' + self.filename
            
            # Directly save to filesystem (bypass create_file/write_file for simplicity)
            # Check if it's a default file being modified
            current_dir = self.filesystem.get_current_directory()
            is_default = ('files' in current_dir and 
                         self.filename in current_dir['files'] and 
                         full_path not in self.filesystem.user_deleted_files)
            
            if full_path in self.filesystem.user_created_files or not is_default:
                # User created file
                self.filesystem.user_created_files[full_path] = self.lines
            else:
                # Modifying a default file
                self.filesystem.user_modified_files[full_path] = self.lines
            
            self.is_modified = False
            self.message = f"Saved: {self.filename}"
            
            # Save filesystem state
            if hasattr(self.previous_state, '_save_filesystem'):
                self.previous_state._save_filesystem()
            
            return True
        except Exception as e:
            self.message = f"Error: {e}"
            return False
    
    def update(self, dt):
        """Update editor state"""
        pass
    
    def render(self):
        """Render the editor"""
        self.renderer.clear()
        
        # Calculate visible area
        max_lines = self.renderer.char_height - 3  # Leave room for status and message
        start_line = max(0, self.current_line - max_lines // 2)
        end_line = min(len(self.lines), start_line + max_lines)
        
        # Draw lines with line numbers
        y = 0
        for i in range(start_line, end_line):
            line_num = str(i + 1).rjust(4)
            is_current = (i == self.current_line)
            
            # Line number
            self.renderer.write(0, y, line_num, (0, 200, 200) if is_current else (100, 100, 100))
            
            # Line content
            line_text = self.lines[i]
            self.renderer.write(5, y, line_text[:self.renderer.char_width - 6], (255, 255, 255))
            
            # Show cursor on current line
            if is_current:
                cursor_x = 5 + min(self.cursor_pos, len(line_text))
                if cursor_x < self.renderer.char_width:
                    if self.editor_name == "emacs" or self.mode == "insert":
                        # Show underscore cursor for emacs and vim insert mode
                        self.renderer.write(cursor_x, y, "_", (255, 255, 0))
                    elif self.mode == "normal":
                        # Show block cursor for vim normal mode
                        char = line_text[self.cursor_pos] if self.cursor_pos < len(line_text) else " "
                        self.renderer.write(cursor_x, y, f"[{char}]", (255, 255, 0))
            
            y += 1
        
        # Status line
        status_y = self.renderer.char_height - 2
        if self.editor_name == "emacs":
            # Emacs-style mode line
            modified_marker = "**" if self.is_modified else "--"
            mode_text = f"-{modified_marker}:--- "
        else:
            mode_text = f"-- {self.mode.upper()} --" if self.mode != "normal" else ""
        file_info = f"{self.filename} [{'modified' if self.is_modified else 'saved'}] {len(self.lines)} lines"
        self.renderer.write(0, status_y, mode_text, (255, 255, 0))
        if self.renderer.char_width - len(file_info) - 1 > 0:
            self.renderer.write(self.renderer.char_width - len(file_info) - 1, status_y, file_info, (150, 150, 150))
        
        # Message line
        msg_y = self.renderer.char_height - 1
        self.renderer.write(0, msg_y, self.message[:self.renderer.char_width], (200, 200, 200))
        
        self.renderer.render()

