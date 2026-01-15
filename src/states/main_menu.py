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
        
        # Easter egg tracking (load from save)
        saved_secrets = game.save_system.get_secrets_found()
        self.secret_commands_found = set(saved_secrets)
        
        # Virtual filesystem (load saved state)
        saved_fs_state = game.save_system.get_filesystem_state()
        self.filesystem = VirtualFileSystem(saved_state=saved_fs_state)
        
        # Konami code tracking
        self.konami_sequence = []
        self.konami_code = ['up', 'up', 'down', 'down', 'left', 'right', 'left', 'right', 'b', 'a']
        
        # Animated typing state
        self.typing_queue = []  # Queue of lines to type out
        self.current_typing_line = ""  # Full line being typed
        self.current_typing_index = 0  # Current character index
        self.typing_timer = 0
        self.typing_delay = 50  # ms between characters
        self.is_typing = False
    
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
                
                # Track Konami code
                self._track_konami_code(event)
                
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
        
        # Animated typing
        if self.is_typing:
            self.typing_timer += dt
            if self.typing_timer >= self.typing_delay:
                self.typing_timer = 0
                
                if self.current_typing_index < len(self.current_typing_line):
                    # Type next character
                    self.current_typing_index += 1
                    # Update the last line in output with current progress
                    if self.output_lines and self.output_lines[-1].startswith(">>> "):
                        self.output_lines[-1] = ">>> " + self.current_typing_line[:self.current_typing_index]
                else:
                    # Finished typing current line
                    # Replace the ">>> " prefix with final text
                    if self.output_lines and self.output_lines[-1].startswith(">>> "):
                        self.output_lines[-1] = self.current_typing_line
                    
                    # Move to next line in queue
                    if self.typing_queue:
                        self._start_typing_next_line()
                    else:
                        self.is_typing = False
    
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
        
        elif ("rm -rf" in cmd_lower or "rm -fr" in cmd_lower) and "save" not in cmd_lower:
            # Easter egg for destructive rm commands (except for save reset)
            self.add_output("ERROR: Cannot delete bullets. They multiply too fast!")
            self.add_output("")
            self._mark_secret_found("destructive")
            return True
        
        elif cmd_lower == "konami":
            self.add_output("↑ ↑ ↓ ↓ ← → ← → B A")
            self.add_output("Classic! But this isn't that kind of game...")
            self.add_output("")
            self._mark_secret_found("konami")
            return True
        
        elif cmd_lower in ["hack", "hack the planet"]:
            self.add_output("HACK THE PLANET!")
            self.add_output("Access granted... to more bullets.")
            self.add_output("")
            self._mark_secret_found("hacker")
            return True
        
        elif cmd_lower == "matrix":
            self.add_output("There is no spoon. Only bullets.")
            self.add_output("")
            self._mark_secret_found("matrix")
            return True
        
        elif cmd_lower == "ping":
            self.add_output("PONG! The bullets hit back.")
            self.add_output("")
            return True
        
        elif cmd_lower == "secret":
            total_found = len(self.secret_commands_found)
            if total_found > 0:
                self.add_output(f"You've found {total_found} secret command(s)!")
                self.add_output(f"Discovered: {', '.join(sorted(self.secret_commands_found))}")
            else:
                self.add_output("No secrets found yet. Keep exploring!")
            self.add_output("")
            return True
        
        elif cmd_lower in ["highscores", "high", "scores"]:
            # Show high scores
            scores = self.game.save_system.get_high_scores(10)
            if scores:
                self.add_output("=== HIGH SCORES ===")
                self.add_output("")
                for i, entry in enumerate(scores, 1):
                    score_val = entry["score"]
                    time_sec = entry["time"] // 1000
                    date_str = entry["date"][:10]  # Just the date part
                    self.add_output(f"{i:2}. {score_val:6} pts  {time_sec:3}s  {date_str}")
                self.add_output("")
            else:
                self.add_output("No high scores yet. Type 'start' to play!")
                self.add_output("")
            return True
        
        elif cmd_lower in ["stats", "statistics"]:
            # Show statistics
            stats = self.game.save_system.get_all_stats()
            total_games = self.game.save_system.data["total_games_played"]
            total_time = self.game.save_system.data["total_time_survived"] // 1000
            exploration = self.game.save_system.get_exploration_stats()
            
            self.add_output("=== STATISTICS ===")
            self.add_output("")
            self.add_output(f"Games Played: {total_games}")
            self.add_output(f"Total Time Survived: {total_time}s")
            self.add_output(f"Enemies Depleted: {stats.get('enemies_depleted', 0)}")
            closest = stats.get('closest_call', 999)
            if closest < 999:
                self.add_output(f"Closest Call: {closest:.2f} tiles")
            self.add_output("")
            self.add_output(f"Secrets Found: {len(self.secret_commands_found)}")
            self.add_output(f"Directories Visited: {exploration['dirs_visited']}")
            self.add_output(f"Files Read: {exploration['files_read']}")
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
            current_path = self.filesystem.get_pwd()
            self.add_output(current_path)
            self.add_output("")
            # Track directory visit
            self.game.save_system.mark_directory_visited(current_path)
        
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
                # Track file read
                current_path = self.filesystem.get_pwd()
                self.game.save_system.mark_file_read(f"{current_path}/{filename}")
            else:
                self.add_output(content)
                self.add_output("")
        
        elif cmd_lower.startswith("touch "):
            # Create empty file
            filename = command[6:].strip()
            success, error = self.filesystem.create_file(filename)
            if success:
                self.add_output(f"Created file: {filename}")
                self._save_filesystem()
            else:
                self.add_output(error)
            self.add_output("")
        
        elif cmd_lower.startswith("mkdir "):
            # Create directory
            dirname = command[6:].strip()
            success, error = self.filesystem.create_directory(dirname)
            if success:
                self.add_output(f"Created directory: {dirname}/")
                self._save_filesystem()
            else:
                self.add_output(error)
            self.add_output("")
        
        elif cmd_lower in ["rm save", "rm save.json", "rm -rf save", "rm -fr save"]:
            # Special command to reset save data
            self.add_output("Deleting save file...")
            self.add_output("")
            self.game.save_system.reset_save()
            # Reset local secrets and filesystem
            self.secret_commands_found = set()
            self.filesystem.reset_to_defaults()
            self.add_output("Save data and filesystem reset! Starting fresh.")
            self.add_output("")
            self._mark_secret_found("fresh_start")
        
        elif cmd_lower.startswith("rm ") and not cmd_lower.startswith("rm -"):
            # Delete file
            filename = command[3:].strip()
            success, error = self.filesystem.delete_file(filename)
            if success:
                self.add_output(f"Deleted: {filename}")
                self._save_filesystem()
            else:
                self.add_output(error)
            self.add_output("")
        
        elif cmd_lower.startswith("rmdir "):
            # Delete directory
            dirname = command[6:].strip()
            success, error = self.filesystem.delete_directory(dirname)
            if success:
                self.add_output(f"Deleted directory: {dirname}/")
                self._save_filesystem()
            else:
                self.add_output(error)
            self.add_output("")
        
        elif cmd_lower.startswith("mv "):
            # Move/rename file
            args = command[3:].strip().split()
            if len(args) == 2:
                source, destination = args
                success, error = self.filesystem.move_file(source, destination)
                if success:
                    self.add_output(f"Moved: {source} -> {destination}")
                    self._save_filesystem()
                else:
                    self.add_output(error)
            else:
                self.add_output("Usage: mv <source> <destination>")
            self.add_output("")
        
        elif " > " in command or " >> " in command:
            # Write to file (echo or other content)
            if " >> " in command:
                parts = command.split(" >> ", 1)
                append = True
            else:
                parts = command.split(" > ", 1)
                append = False
            
            if len(parts) == 2:
                content_part = parts[0].strip()
                filename = parts[1].strip()
                
                # Extract content (handle echo specially)
                if content_part.startswith("echo "):
                    content = content_part[5:].strip().strip('"').strip("'")
                else:
                    content = content_part
                
                # Create file if it doesn't exist
                if not self.filesystem.file_exists(filename):
                    self.filesystem.create_file(filename, "")
                
                success, error = self.filesystem.write_file(filename, content, append=append)
                if success:
                    action = "Appended to" if append else "Wrote to"
                    self.add_output(f"{action}: {filename}")
                    self._save_filesystem()
                else:
                    self.add_output(error)
                self.add_output("")
            else:
                self.add_output("Invalid syntax. Use: echo text > file  or  echo text >> file")
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
        # Get all contents (includes user-created)
        all_contents = self.filesystem.list_directory()
        
        # Filter for directories (end with /)
        matches = []
        for item in all_contents:
            if item.endswith('/'):
                dir_name = item[:-1]  # Remove trailing slash
                if dir_name.startswith(partial):
                    matches.append(dir_name)
        
        # Also include .. if it starts with partial
        if "..".startswith(partial) and len(self.filesystem.current_path) > 1:
            matches.append("..")
        
        return sorted(matches)
    
    def _get_file_completions(self, partial):
        """Get file name completions"""
        # Get all contents (includes user-created)
        all_contents = self.filesystem.list_directory()
        
        # Filter for files (don't end with /)
        matches = []
        for item in all_contents:
            if not item.endswith('/'):
                if item.startswith(partial):
                    matches.append(item)
        
        return sorted(matches)
    
    def _track_konami_code(self, event):
        """Track key presses for Konami code detection"""
        key_name = None
        
        # Map pygame keys to our sequence names
        if event.key == pygame.K_UP:
            key_name = 'up'
        elif event.key == pygame.K_DOWN:
            key_name = 'down'
        elif event.key == pygame.K_LEFT:
            key_name = 'left'
        elif event.key == pygame.K_RIGHT:
            key_name = 'right'
        elif event.unicode.lower() == 'b':
            key_name = 'b'
        elif event.unicode.lower() == 'a':
            key_name = 'a'
        
        if key_name:
            # Add to sequence
            self.konami_sequence.append(key_name)
            
            # Keep only the last 10 keys (length of Konami code)
            if len(self.konami_sequence) > 10:
                self.konami_sequence.pop(0)
            
            # Check if we've completed the Konami code
            if self.konami_sequence == self.konami_code:
                self.add_output("")
                # Use animated typing for dramatic effect
                self.type_output([
                    "...",
                    "....",
                    "Psh, your powers don't work here.",
                    "This is a bullet hell, not Contra!",
                    ""
                ], delay=30)
                self._mark_secret_found("konami_keys")
                # Reset sequence
                self.konami_sequence = []
    
    def _mark_secret_found(self, secret_id):
        """Mark a secret as found and save"""
        self.secret_commands_found.add(secret_id)
        self.game.save_system.add_secret_found(secret_id)
    
    def _save_filesystem(self):
        """Save current filesystem state"""
        fs_state = self.filesystem.get_state()
        self.game.save_system.save_filesystem(fs_state)
    
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
        """Add a line to the output buffer instantly"""
        self.output_lines.append(text)
        
        # Trim old lines if too many
        if len(self.output_lines) > 1000:
            self.output_lines = self.output_lines[-1000:]
    
    def type_output(self, text_lines, delay=50):
        """
        Add lines to output with animated typing effect
        
        Args:
            text_lines: String or list of strings to type out
            delay: Milliseconds between characters (default 50)
        """
        # Convert single string to list
        if isinstance(text_lines, str):
            text_lines = [text_lines]
        
        # Add lines to typing queue
        self.typing_queue.extend(text_lines)
        self.typing_delay = delay
        
        # Start typing if not already typing
        if not self.is_typing:
            self._start_typing_next_line()
    
    def _start_typing_next_line(self):
        """Start typing the next line in the queue"""
        if self.typing_queue:
            self.current_typing_line = self.typing_queue.pop(0)
            self.current_typing_index = 0
            self.is_typing = True
            self.typing_timer = 0
            # Add placeholder line with ">>> " prefix to show it's typing
            self.output_lines.append(">>> ")
        else:
            self.is_typing = False
    
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
