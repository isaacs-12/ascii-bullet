"""Main menu state with terminal command interface"""

import pygame
from src.states.base_state import BaseState
from src.ascii_art import (
    BLTHLL_ASCII, get_startup_sequence, get_welcome_text,
    get_help_text, get_about_text
)
from src.filesystem import VirtualFileSystem


class MainMenuState(BaseState):
    """Terminal-style command interface main menu"""
    
    def __init__(self, game):
        super().__init__(game)
        
        # Terminal state
        self.output_lines = []
        self.input_buffer = ""
        self.cursor_visible = True
        self.cursor_timer = 0
        self.max_lines = self.renderer.char_height - 2  # Leave room for input
        
        # Boot sequence state
        self.booting = True
        self.boot_sequence = get_startup_sequence()
        self.boot_index = 0
        self.boot_timer = 0
        self.boot_delay = 200  # ms between boot lines
        
        # Command history
        self.command_history = []
        self.history_index = -1
        
        # Easter egg tracking
        self.secret_commands_found = set()
        
        # Virtual filesystem
        self.filesystem = VirtualFileSystem()
    
    def enter(self):
        """Called when entering this state"""
        # Start with boot sequence
        self.booting = True
        self.boot_index = 0
        self.boot_timer = 0
        self.output_lines = []
    
    def handle_events(self, events):
        """Handle keyboard input for terminal"""
        for event in events:
            if event.type == pygame.KEYDOWN:
                if self.booting:
                    # Skip boot sequence on any key
                    self.complete_boot()
                    return
                
                if event.key == pygame.K_RETURN:
                    # Execute command
                    self.execute_command(self.input_buffer.strip())
                    self.input_buffer = ""
                    self.history_index = -1
                
                elif event.key == pygame.K_BACKSPACE:
                    # Delete last character
                    if self.input_buffer:
                        self.input_buffer = self.input_buffer[:-1]
                
                elif event.key == pygame.K_UP:
                    # Navigate command history up
                    if self.command_history and self.history_index < len(self.command_history) - 1:
                        self.history_index += 1
                        self.input_buffer = self.command_history[-(self.history_index + 1)]
                
                elif event.key == pygame.K_DOWN:
                    # Navigate command history down
                    if self.history_index > 0:
                        self.history_index -= 1
                        self.input_buffer = self.command_history[-(self.history_index + 1)]
                    elif self.history_index == 0:
                        self.history_index = -1
                        self.input_buffer = ""
                
                elif event.key == pygame.K_TAB:
                    # Tab completion for cd and cat commands
                    self._handle_tab_completion()
                
                elif event.key == pygame.K_ESCAPE:
                    # Quick quit
                    self.game.running = False
                
                elif event.unicode and event.unicode.isprintable():
                    # Add character to input buffer
                    prompt_len = len(self.get_prompt())
                    if len(self.input_buffer) < self.renderer.char_width - prompt_len - 2:
                        self.input_buffer += event.unicode
    
    def update(self, dt):
        """Update terminal state"""
        # Update cursor blink
        self.cursor_timer += dt
        if self.cursor_timer >= 500:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0
        
        # Handle boot sequence
        if self.booting:
            self.boot_timer += dt
            if self.boot_timer >= self.boot_delay:
                if self.boot_index < len(self.boot_sequence):
                    self.output_lines.append(self.boot_sequence[self.boot_index])
                    self.boot_index += 1
                    self.boot_timer = 0
                else:
                    # Boot complete, show title and welcome
                    self.complete_boot()
    
    def complete_boot(self):
        """Complete the boot sequence and show main screen"""
        self.booting = False
        self.output_lines = []
        
        # Add ASCII title
        for line in BLTHLL_ASCII:
            self.output_lines.append(line)
        self.output_lines.append("")
        
        # Add welcome text
        for line in get_welcome_text():
            self.output_lines.append(line)

    def _easter_egg_commands(self, cmd_lower):
        """
        Handle easter egg commands
        
        Args:
            cmd_lower: The lowercase command string
            
        Returns:
            True if command was handled, False otherwise
        """
        # Easter eggs!
        if cmd_lower in ["hello", "hi"]:
            self.add_output("Hello, human. Ready to dodge some bullets?")
            self.add_output("")
            return True
        
        elif cmd_lower == "whoami":
            self.add_output("You are a brave pilot in a world of bullets.")
            self.add_output("")
            return True
        
        elif cmd_lower in ["sudo", "sudo su"]:
            self.add_output("Nice try. You already have all the permissions here.")
            self.add_output("")
            return True
        
        elif "rm -rf" in cmd_lower or "rm -fr" in cmd_lower:
            self.add_output("ERROR: Cannot delete bullets. They multiply too fast!")
            self.add_output("")
            self.secret_commands_found.add("destructive")
            return True
        
        elif cmd_lower == "konami":
            self.add_output("↑ ↑ ↓ ↓ ← → ← → B A")
            self.add_output("Classic! But this isn't that kind of game...")
            self.add_output("")
            self.secret_commands_found.add("konami")
            return True
        
        elif cmd_lower in ["hack", "hack the planet"]:
            self.add_output("HACK THE PLANET!")
            self.add_output("Access granted... to more bullets.")
            self.add_output("")
            self.secret_commands_found.add("hacker")
            return True
        
        elif cmd_lower == "matrix":
            self.add_output("There is no spoon. Only bullets.")
            self.add_output("")
            self.secret_commands_found.add("matrix")
            return True
        
        elif cmd_lower == "ping":
            self.add_output("PONG! The bullets hit back.")
            self.add_output("")
            return True
        
        elif cmd_lower == "secret":
            if len(self.secret_commands_found) > 0:
                self.add_output(f"You've found {len(self.secret_commands_found)} secret command(s)!")
                self.add_output(f"Discovered: {', '.join(sorted(self.secret_commands_found))}")
            else:
                self.add_output("No secrets found yet. Keep exploring!")
            self.add_output("")
            return True
        
        # Command not recognized as an easter egg
        return False
    
    def execute_command(self, command):
        """
        Execute a terminal command
        
        Args:
            command: The command string entered by user
        """
        if not command:
            return
        
        # Add to history
        self.command_history.append(command)
        
        # Show command in output
        self.add_output(f"{self.get_prompt()}{command}")
        
        # Parse and execute
        cmd_lower = command.lower()
        
        if cmd_lower in ["start", "new", "newgame", "new game", "begin"]:
            self.add_output("Starting new game...")
            self.add_output("")
            # Launch gameplay state, passing this menu state to return to
            from src.states.gameplay import GameplayState
            self.game.change_state(GameplayState(self.game, previous_state=self))
        
        elif cmd_lower in ["continue", "load", "resume"]:
            self.add_output("Loading saved game...")
            self.add_output("(Save system not implemented yet)")
            self.add_output("")
        
        elif cmd_lower in ["quit", "exit", "q"]:
            self.add_output("Shutting down...")
            self.game.running = False
        
        elif cmd_lower in ["help", "?", "commands"]:
            for line in get_help_text():
                self.add_output(line)
        
        elif cmd_lower in ["about", "info", "version"]:
            for line in get_about_text():
                self.add_output(line)
        
        elif cmd_lower in ["clear", "cls"]:
            self.output_lines = []
        
        elif cmd_lower in ["ls", "dir"]:
            # List directory contents
            contents = self.filesystem.list_directory()
            if contents:
                # Format in columns for better display
                self.add_output("  ".join(contents))
            else:
                self.add_output("(empty directory)")
            self.add_output("")
        
        elif cmd_lower == "pwd":
            # Print working directory
            self.add_output(self.filesystem.get_pwd())
            self.add_output("")
        
        elif cmd_lower.startswith("cd "):
            # Change directory
            path = command[3:].strip()
            success, error = self.filesystem.change_directory(path)
            if not success:
                self.add_output(error)
                self.add_output("")
        
        elif cmd_lower.startswith("cat "):
            # Read file
            filename = command[4:].strip()
            success, content = self.filesystem.read_file(filename)
            if success:
                for line in content:
                    self.add_output(line)
                self.add_output("")
            else:
                self.add_output(content)
                self.add_output("")
        
        elif self._easter_egg_commands(cmd_lower=cmd_lower):
            return
        
        else:
            self.add_output(f"Command not found: {command}")
            self.add_output("Type 'help' for available commands")
            self.add_output("")
    
    def _handle_tab_completion(self):
        """Handle tab completion for cd and cat commands"""
        if not self.input_buffer:
            return
        
        parts = self.input_buffer.split()
        if len(parts) == 0:
            return
        
        command = parts[0].lower()
        
        # Only support completion for cd and cat
        if command not in ['cd', 'cat']:
            return
        
        # Get the partial path/filename being typed
        if len(parts) == 1:
            partial = ""
        else:
            partial = parts[1]
        
        # Get appropriate completions
        if command == 'cd':
            completions = self._get_directory_completions(partial)
        else:  # cat
            completions = self._get_file_completions(partial)
        
        if not completions:
            return
        
        # If only one completion, auto-complete it
        if len(completions) == 1:
            if len(parts) == 1:
                self.input_buffer = f"{command} {completions[0]}"
            else:
                self.input_buffer = f"{command} {completions[0]}"
        else:
            # Multiple completions - show them
            self.add_output("")
            self.add_output("  ".join(completions))
            self.add_output("")
    
    def _get_directory_completions(self, partial):
        """Get directory name completions"""
        current_dir = self.filesystem.get_current_directory()
        
        if 'dirs' not in current_dir:
            return []
        
        # Get all directories that start with the partial string
        matches = []
        for dir_name in current_dir['dirs'].keys():
            if dir_name.startswith(partial):
                matches.append(dir_name)
        
        # Also include .. if it starts with partial
        if "..".startswith(partial) and len(self.filesystem.current_path) > 1:
            matches.append("..")
        
        return sorted(matches)
    
    def _get_file_completions(self, partial):
        """Get file name completions"""
        current_dir = self.filesystem.get_current_directory()
        
        if 'files' not in current_dir:
            return []
        
        # Get all files that start with the partial string
        matches = []
        for file_name in current_dir['files'].keys():
            if file_name.startswith(partial):
                matches.append(file_name)
        
        return sorted(matches)
    
    def get_prompt(self):
        """Get the current prompt string with directory"""
        # Get just the last part of the path for brevity
        path_parts = self.filesystem.current_path
        if path_parts:
            current_dir = path_parts[-1]
        else:
            current_dir = "~"
        return f"[{current_dir}]> "
    
    def add_output(self, text):
        """Add a line to the output buffer"""
        self.output_lines.append(text)
        
        # Trim old lines if too many
        if len(self.output_lines) > 1000:
            self.output_lines = self.output_lines[-1000:]
    
    def render(self):
        """Render the terminal interface"""
        self.renderer.clear()
        
        # Calculate visible area
        visible_lines = self.renderer.char_height - 2  # Leave space for input line
        
        # Get the lines to display (most recent ones)
        start_idx = max(0, len(self.output_lines) - visible_lines)
        visible_output = self.output_lines[start_idx:]
        
        # Draw output lines
        for i, line in enumerate(visible_output):
            self.renderer.write(1, i + 1, line[:self.renderer.char_width - 2])
        
        # Draw input line at bottom
        input_y = self.renderer.char_height - 1
        
        # Draw border line
        self.renderer.write(0, input_y - 1, "-" * self.renderer.char_width, 
                          self.renderer.COLORS['menu_normal'])
        
        # Draw prompt and input
        prompt = self.get_prompt()
        input_text = prompt + self.input_buffer
        self.renderer.write(0, input_y, input_text, self.renderer.COLORS['menu_selected'])
        
        # Draw cursor
        if self.cursor_visible and not self.booting:
            cursor_x = len(input_text)
            if cursor_x < self.renderer.char_width:
                self.renderer.write(cursor_x, input_y, "█", self.renderer.COLORS['menu_selected'])
        
        # If booting, show "Press any key" hint
        if self.booting and self.boot_index >= len(self.boot_sequence):
            hint_y = self.renderer.char_height - 3
            hint = "[Press any key to continue]"
            self.renderer.write_centered(hint_y, hint, self.renderer.COLORS['menu_normal'])
        
        self.renderer.render()
