"""Main menu state with terminal command interface"""

import pygame
from src.states.base_state import BaseState
from src.ascii_art import (
    BLTHLL_ASCII, get_startup_sequence, get_welcome_text,
    get_help_text, get_about_text
)


class MainMenuState(BaseState):
    """Terminal-style command interface main menu"""
    
    def __init__(self, game):
        super().__init__(game)
        
        # Terminal state
        self.output_lines = []
        self.input_buffer = ""
        self.prompt = "> "
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
                
                elif event.key == pygame.K_ESCAPE:
                    # Quick quit
                    self.game.running = False
                
                elif event.unicode and event.unicode.isprintable():
                    # Add character to input buffer
                    if len(self.input_buffer) < self.renderer.char_width - len(self.prompt) - 2:
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
        self.add_output(f"{self.prompt}{command}")
        
        # Parse and execute
        cmd_lower = command.lower()
        
        if cmd_lower in ["start", "new", "newgame", "new game", "begin"]:
            self.add_output("Starting new game...")
            self.add_output("(Game state not implemented yet)")
            self.add_output("")
        
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
        
        # Easter eggs!
        elif cmd_lower in ["hello", "hi"]:
            self.add_output("Hello, human. Ready to dodge some bullets?")
            self.add_output("")
        
        elif cmd_lower == "whoami":
            self.add_output("You are a brave pilot in a world of bullets.")
            self.add_output("")
        
        elif cmd_lower in ["sudo", "sudo su"]:
            self.add_output("Nice try. You already have all the permissions here.")
            self.add_output("")
        
        elif "rm -rf" in cmd_lower or "rm -fr" in cmd_lower:
            self.add_output("ERROR: Cannot delete bullets. They multiply too fast!")
            self.add_output("")
            self.secret_commands_found.add("destructive")
        
        elif cmd_lower == "konami":
            self.add_output("↑ ↑ ↓ ↓ ← → ← → B A")
            self.add_output("Classic! But this isn't that kind of game...")
            self.add_output("")
            self.secret_commands_found.add("konami")
        
        elif cmd_lower in ["hack", "hack the planet"]:
            self.add_output("HACK THE PLANET!")
            self.add_output("Access granted... to more bullets.")
            self.add_output("")
            self.secret_commands_found.add("hacker")
        
        elif cmd_lower == "matrix":
            self.add_output("There is no spoon. Only bullets.")
            self.add_output("")
            self.secret_commands_found.add("matrix")
        
        elif cmd_lower in ["ls", "dir"]:
            self.add_output("bullets.dat  more_bullets.dat  even_more_bullets.dat")
            self.add_output("")
        
        elif cmd_lower == "cat bullets.dat":
            self.add_output("░▒▓█ BULLET DATA █▓▒░")
            self.add_output("◉ ◎ ● ○ ◐ ◑ ◒ ◓ ◔ ◕")
            self.add_output("")
        
        elif cmd_lower == "pwd":
            self.add_output("/home/pilot/blthll/certain_death")
            self.add_output("")
        
        elif cmd_lower == "ping":
            self.add_output("PONG! The bullets hit back.")
            self.add_output("")
        
        elif cmd_lower == "secret":
            if len(self.secret_commands_found) > 0:
                self.add_output(f"You've found {len(self.secret_commands_found)} secret command(s)!")
                self.add_output(f"Discovered: {', '.join(sorted(self.secret_commands_found))}")
            else:
                self.add_output("No secrets found yet. Keep exploring!")
            self.add_output("")
        
        else:
            self.add_output(f"Command not found: {command}")
            self.add_output("Type 'help' for available commands")
            self.add_output("")
    
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
        self.renderer.write(0, input_y - 1, "─" * self.renderer.char_width, 
                          self.renderer.COLORS['frame_highlight'])
        
        # Draw prompt and input
        input_text = self.prompt + self.input_buffer
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
