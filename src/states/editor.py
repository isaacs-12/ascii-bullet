"""
Simple text editor state for editing files in the virtual filesystem
"""

import pygame
from src.states.base_state import BaseState


class EditorState(BaseState):
    """A basic text editor for the virtual filesystem"""
    
    def __init__(self, game, filesystem, filename, previous_state):
        """
        Initialize the editor
        
        Args:
            game: Game instance
            filesystem: VirtualFileSystem instance
            filename: Name of file to edit
            previous_state: State to return to when done
        """
        print(f"[DEBUG] EditorState.__init__ called with filename: {filename}")
        try:
            super().__init__(game)
            print(f"[DEBUG] super().__init__ successful")
            self.filesystem = filesystem
            self.filename = filename
            self.previous_state = previous_state
            
            # Editor state
            self.lines = []
            self.current_line = 0
            self.cursor_pos = 0
            self.mode = "normal"  # "normal", "insert", or "command"
            self.command_buffer = ""
            self.message = ""
            self.is_modified = False
            print(f"[DEBUG] Editor state variables initialized")
            
            # Load file if it exists
            print(f"[DEBUG] Attempting to read file: {filename}")
            success, content = filesystem.read_file(filename)
            print(f"[DEBUG] File read result: success={success}, content type={type(content)}")
            if success:
                if isinstance(content, list):
                    self.lines = [str(line) for line in content]
                else:
                    self.lines = [str(content)]
                print(f"[DEBUG] Loaded {len(self.lines)} lines")
            else:
                # New file
                self.lines = [""]
                print(f"[DEBUG] New file, starting with empty line")
            
            # Ensure at least one line
            if not self.lines:
                self.lines = [""]
                
            print(f"[DEBUG] EditorState.__init__ completed successfully")
        except Exception as e:
            print(f"[ERROR] Exception in EditorState.__init__: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def enter(self):
        """Called when entering this state"""
        print(f"[DEBUG] EditorState.enter() called")
        try:
            self.message = f"Editing: {self.filename} | ESC=normal, i=insert, :w=save, :q=quit, :wq=save&quit"
            print(f"[DEBUG] EditorState.enter() completed")
        except Exception as e:
            print(f"[ERROR] Exception in EditorState.enter(): {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def exit(self):
        """Called when exiting this state"""
        pass
    
    def handle_events(self, events):
        """Handle input events"""
        for event in events:
            if event.type == pygame.KEYDOWN:
                if self.mode == "normal":
                    self._handle_normal_mode(event)
                elif self.mode == "insert":
                    self._handle_insert_mode(event)
                elif self.mode == "command":
                    self._handle_command_mode(event)
    
    def _handle_normal_mode(self, event):
        """Handle keys in normal mode"""
        if event.key == pygame.K_ESCAPE:
            # Return to previous state
            if self.is_modified:
                self.message = "Warning: Unsaved changes! Use :w to save or :q! to quit without saving"
            else:
                self.game.change_state(self.previous_state, call_enter=False)
        
        elif event.key == pygame.K_i:
            # Enter insert mode
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
        # print(f"[DEBUG] EditorState.update() called with dt={dt}")  # Too verbose
        pass
    
    def render(self):
        """Render the editor"""
        print(f"[DEBUG] EditorState.render() called")
        try:
            print(f"[DEBUG] Clearing renderer...")
            self.renderer.clear()
            
            print(f"[DEBUG] Calculating visible area, char_height={self.renderer.char_height}")
            # Calculate visible area
            max_lines = self.renderer.char_height - 3  # Leave room for status and message
            start_line = max(0, self.current_line - max_lines // 2)
            end_line = min(len(self.lines), start_line + max_lines)
            print(f"[DEBUG] Visible area: lines {start_line} to {end_line}")
        except Exception as e:
            print(f"[ERROR] Error in editor render setup: {e}")
            import traceback
            traceback.print_exc()
            return
        
        try:
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
                if is_current and self.mode == "insert":
                    cursor_x = 5 + min(self.cursor_pos, len(line_text))
                    if cursor_x < self.renderer.char_width:
                        self.renderer.write(cursor_x, y, "_", (255, 255, 0))
                elif is_current and self.mode == "normal":
                    cursor_x = 5 + min(self.cursor_pos, len(line_text))
                    if cursor_x < self.renderer.char_width:
                        # Show cursor as highlighted character in normal mode
                        char = line_text[self.cursor_pos] if self.cursor_pos < len(line_text) else " "
                        self.renderer.write(cursor_x, y, f"[{char}]", (255, 255, 0))
                
                y += 1
            
            # Status line
            status_y = self.renderer.char_height - 2
            mode_text = f"-- {self.mode.upper()} --" if self.mode != "normal" else ""
            file_info = f"{self.filename} [{'modified' if self.is_modified else 'saved'}] {len(self.lines)} lines"
            self.renderer.write(0, status_y, mode_text, (255, 255, 0))
            if self.renderer.char_width - len(file_info) - 1 > 0:
                self.renderer.write(self.renderer.char_width - len(file_info) - 1, status_y, file_info, (150, 150, 150))
            
            # Message line
            msg_y = self.renderer.char_height - 1
            self.renderer.write(0, msg_y, self.message[:self.renderer.char_width], (200, 200, 200))
            
            self.renderer.render()
        except Exception as e:
            print(f"Error rendering editor: {e}")
            import traceback
            traceback.print_exc()

