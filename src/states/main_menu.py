"""Main menu state with terminal command interface"""

import pygame
from src.states.base_state import BaseState
from src.core.ascii_art import (
    BLTHLL_ASCII, get_startup_sequence, get_welcome_text,
    get_help_text, get_about_text
)
from src.core.puzzle_system import check_puzzles, get_unlocked_game_help_lines
from src.unix.filesystem import VirtualFileSystem
from src.unix.text_editor import TextEditor


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
        self.scroll_offset = 0  # How many lines to scroll back (0 = show most recent)
        
        # Smooth scrolling state
        self.scroll_direction = 0  # -1 = up, 1 = down, 0 = none
        self.scroll_accumulator = 0.0  # Accumulated scroll time
        self.scroll_rate = 5.0  # Lines per second when holding
        
        # Boot sequence state
        self.booting = True
        self.boot_sequence = get_startup_sequence()
        self.boot_index = 0
        self.boot_timer = 0
        self.boot_delay = 200  # ms between boot lines
        
        # Intro sequence state
        self.showing_intro = False
        self.intro_page = 0  # 0 = page 1, 1 = page 2, 2 = done
        self.intro_waiting_for_key = False
        
        # Save prompt state (for built games with existing saves)
        self.showing_save_prompt = False
        self.save_prompt_waiting_for_input = False
        self.intro_text_pages = [
            [
                "Welcome to BLLTHLL. What you're looking at isn't your computer's terminal.",
                "...",
                "We here at Walnut Industries have taken control of your computer, and locked",
                "your super sick games library behind a series of puzzles (I'm maniacally",
                "laughing, I wish you could hear it)",
                "...",
                "In order to progress through this game, er, test... I mean test... you will",
                "need to discover a decidedly finite quantity of secrets, possible only by",
                "demonstrating technical proficiency.",
                "",
                "(Press any key to continue)"
            ],
            [
                "In this computer we've left you with are a selection of tools you might know",
                "well, or that you might need some introduction to. We don't want you to be",
                "totally alone, so you can always use `help` as a reminder of what you have at",
                "your disposal.Solutions to puzzles can usually be found multiple ways, but",
                "as a tip, look around in the filesystem, and remember the tools we've given you.",
                "...",
                "If you'd rather play games, we give you one for each puzzle you solve...",
                "And you can also use Python to help you solve puzzles too, though we've limited",
                "its use here so as not to make it too powerful.",
                "...",
                "Good luck.",
                "",
                "(Press any key to continue)"
            ]
        ]
        
        # Command history (load from save)
        saved_history = game.save_system.get_command_history()
        self.command_history = saved_history.copy() if saved_history else []
        self.history_index = -1
        
        # Easter egg tracking (load from save)
        saved_secrets = game.save_system.get_secrets_found()
        self.secret_commands_found = set(saved_secrets)
        
        # Virtual filesystem (load saved state)
        saved_fs_state = game.save_system.get_filesystem_state()
        self.filesystem = VirtualFileSystem(saved_state=saved_fs_state)
        
        # Process manager
        from src.unix.process_manager import ProcessManager
        self.process_manager = ProcessManager(save_system=game.save_system)
        
        # Systemd manager
        from src.unix.systemd_manager import SystemdManager
        self.systemd_manager = SystemdManager(self.filesystem, save_system=game.save_system)
        
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
        
        # Text editor state
        self.editor = None
        self.editor_active = False
        self.editor_filename = None
        
        # Sudo authentication state
        self.sudo_authenticated = False
        self.sudo_timestamp = 0
        self.sudo_timeout = 300000  # 5 minutes in milliseconds
        self.sudo_password = "WallySmith"
        self.waiting_for_password = False
        self.pending_sudo_command = None
        self.password_buffer = ""
    
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
                # Handle save prompt (for built games with existing saves)
                if self.showing_save_prompt:
                    if not self.is_typing and not self.save_prompt_waiting_for_input and not self.typing_queue:
                        self.save_prompt_waiting_for_input = True
                    
                    if self.save_prompt_waiting_for_input and not self.is_typing:
                        # Process yes/no input
                        if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                            response = self.input_buffer.strip().lower()
                            self.input_buffer = ""
                            
                            if response in ['yes', 'y']:
                                # User wants to use existing save
                                self.add_output("Loading existing save...")
                                self.add_output("")
                                # Reload save data (it's already loaded, but mark prompt as shown)
                                self.game.save_system.mark_save_prompt_shown()
                                # Reload data from file to ensure we have the latest
                                self.game.save_system.data = self.game.save_system._load()
                                # Reload filesystem state
                                saved_fs_state = self.game.save_system.get_filesystem_state()
                                self.filesystem = VirtualFileSystem(saved_state=saved_fs_state)
                                # Reload secrets
                                saved_secrets = self.game.save_system.get_secrets_found()
                                self.secret_commands_found = set(saved_secrets)
                                # Continue to intro or main screen
                                self.showing_save_prompt = False
                                if not self.game.save_system.has_intro_been_shown():
                                    self.showing_intro = True
                                    self.intro_page = 0
                                    self.intro_waiting_for_key = False
                                    self._start_intro_page(0)
                                else:
                                    self._show_main_screen()
                            elif response in ['no', 'n']:
                                # User wants to start fresh
                                self.add_output("Starting fresh...")
                                self.add_output("")
                                # Reset save to default
                                self.game.save_system.reset_save()
                                self.game.save_system.mark_save_prompt_shown()
                                # Reload filesystem with fresh state
                                self.filesystem = VirtualFileSystem(saved_state=None)
                                self.secret_commands_found = set()
                                # Continue to intro or main screen
                                self.showing_save_prompt = False
                                if not self.game.save_system.has_intro_been_shown():
                                    self.showing_intro = True
                                    self.intro_page = 0
                                    self.intro_waiting_for_key = False
                                    self._start_intro_page(0)
                                else:
                                    self._show_main_screen()
                            else:
                                # Invalid input, ask again
                                self.add_output("Please type 'yes' or 'no'.")
                                self.add_output("")
                                self.add_output("> ")
                                return
                        elif event.key == pygame.K_BACKSPACE:
                            if len(self.input_buffer) > 0:
                                self.input_buffer = self.input_buffer[:-1]
                        elif event.unicode and event.unicode.isprintable():
                            self.input_buffer += event.unicode
                        return  # Don't process other keys during save prompt
                
                # Handle intro sequence
                if self.showing_intro:
                    # If typing is complete and we're not already waiting, mark as waiting
                    if not self.is_typing and not self.intro_waiting_for_key and not self.typing_queue:
                        self.intro_waiting_for_key = True
                    
                    # If waiting for key, any key press advances to next page
                    if self.intro_waiting_for_key and not self.is_typing:
                        self.intro_page += 1
                        if self.intro_page < len(self.intro_text_pages):
                            # Show next page
                            self._start_intro_page(self.intro_page)
                        else:
                            # Intro complete, show main screen
                            self.showing_intro = False
                            self.game.save_system.mark_intro_shown()
                            self._show_main_screen()
                        return  # Don't process other keys during intro
                
                # Handle text editor if active
                if self.editor_active and self.editor:
                    self.editor.handle_event(event)
                    
                    # Check if editor wants to exit
                    if self.editor.should_exit:
                        self.editor_active = False
                        self.add_output(f"Exited editor: {self.editor_filename}")
                        self.add_output("")
                        self.editor = None
                        self.editor_filename = None
                    
                    # Check if editor wants to save
                    elif self.editor.should_save:
                        content = self.editor.get_content()
                        success, error = self.filesystem.create_file(
                            self.editor_filename, 
                            content
                        )
                        if success:
                            self._save_filesystem()
                        self.editor.should_save = False
                    
                    continue
                
                if self.booting:
                    # Skip boot sequence on any key
                    self.complete_boot()
                    return
                
                # Track Konami code
                self._track_konami_code(event)
                
                if event.key == pygame.K_RETURN:
                    # Don't process normal commands during save prompt
                    if self.showing_save_prompt:
                        return
                    # Check if waiting for password
                    if self.waiting_for_password:
                        self._check_sudo_password(self.password_buffer)
                        self.password_buffer = ""
                        self.waiting_for_password = False
                        self.input_buffer = ""
                    else:
                        # Execute command normally
                        self.execute_command(self.input_buffer.strip())
                        self.input_buffer = ""
                        self.history_index = -1
                
                elif event.key == pygame.K_BACKSPACE:
                    # Delete last character
                    # If user starts editing after navigating history, reset history index
                    if self.history_index != -1:
                        self.history_index = -1
                    if self.waiting_for_password:
                        if self.password_buffer:
                            self.password_buffer = self.password_buffer[:-1]
                            if self.input_buffer:
                                self.input_buffer = self.input_buffer[:-1]
                    elif self.input_buffer:
                        self.input_buffer = self.input_buffer[:-1]
                
                elif event.key == pygame.K_UP:
                    # Shift+UP scrolls output, otherwise navigate history
                    if event.mod & pygame.KMOD_SHIFT:
                        # Start smooth scrolling up
                        self.scroll_direction = -1
                        # Also scroll one line immediately
                        visible_lines = self.renderer.char_height - 2
                        max_scroll = max(0, len(self.output_lines) - visible_lines)
                        self.scroll_offset = min(max_scroll, self.scroll_offset + 1)
                    else:
                        # Navigate command history up (most recent first)
                        if self.command_history:
                            if self.history_index < len(self.command_history) - 1:
                                self.history_index += 1
                                # Access from end: history_index 0 = most recent, 1 = second most recent, etc.
                                self.input_buffer = self.command_history[-(self.history_index + 1)]
                
                elif event.key == pygame.K_DOWN:
                    # Shift+DOWN scrolls output, otherwise navigate history
                    if event.mod & pygame.KMOD_SHIFT:
                        # Start smooth scrolling down
                        self.scroll_direction = 1
                        # Also scroll one line immediately
                        self.scroll_offset = max(0, self.scroll_offset - 1)
                    else:
                        # Navigate command history down
                        if self.history_index > 0:
                            self.history_index -= 1
                            self.input_buffer = self.command_history[-(self.history_index + 1)]
                        elif self.history_index == 0:
                            self.history_index = -1
                            self.input_buffer = ""
                
                elif event.key == pygame.K_PAGEUP:
                    # Scroll output up by page
                    visible_lines = self.renderer.char_height - 2
                    page_size = visible_lines
                    max_scroll = max(0, len(self.output_lines) - visible_lines)
                    self.scroll_offset = min(max_scroll, self.scroll_offset + page_size)
                
                elif event.key == pygame.K_PAGEDOWN:
                    # Scroll output down by page
                    visible_lines = self.renderer.char_height - 2
                    page_size = visible_lines
                    self.scroll_offset = max(0, self.scroll_offset - page_size)
                
                elif event.key == pygame.K_HOME:
                    # Scroll to top (oldest output)
                    visible_lines = self.renderer.char_height - 2
                    max_scroll = max(0, len(self.output_lines) - visible_lines)
                    self.scroll_offset = max_scroll
                
                elif event.key == pygame.K_END:
                    # Scroll to bottom (newest output)
                    self.scroll_offset = 0
                
                elif event.key == pygame.K_TAB:
                    # Tab completion for cd and cat commands
                    self._handle_tab_completion()
                
                elif event.key == pygame.K_ESCAPE:
                    # Clear input buffer or cancel current operation
                    if self.waiting_for_password:
                        # Cancel password prompt
                        self.waiting_for_password = False
                        self.password_buffer = ""
                        self.pending_sudo_command = None
                        self.input_buffer = ""
                    elif self.input_buffer:
                        # Clear input buffer
                        self.input_buffer = ""
                        self.history_index = -1
                    else:
                        # If input is already empty, do nothing (or could quit with double-ESC)
                        pass
                
                elif event.unicode and event.unicode.isprintable():
                    # Add character to input buffer
                    prompt_len = len(self.get_prompt())
                    if len(self.input_buffer) < self.renderer.char_width - prompt_len - 2:
                        if self.waiting_for_password:
                            # Store actual character but display asterisk
                            self.password_buffer += event.unicode
                            self.input_buffer += '*'
                        else:
                            # If user starts typing after navigating history, reset history index
                            if self.history_index != -1:
                                self.history_index = -1
                            self.input_buffer += event.unicode
    
    def update(self, dt):
        """Update terminal state"""
        # Update cursor blink
        self.cursor_timer += dt
        if self.cursor_timer >= 500:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0
        
        # Handle smooth scrolling when Shift+Arrow keys are held
        keys = pygame.key.get_pressed()
        shift_held = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        
        if shift_held:
            if keys[pygame.K_UP]:
                # Smooth scroll up
                self.scroll_direction = -1
            elif keys[pygame.K_DOWN]:
                # Smooth scroll down
                self.scroll_direction = 1
            else:
                # No arrow key held, stop scrolling
                self.scroll_direction = 0
                self.scroll_accumulator = 0.0
        else:
            # Shift not held, stop scrolling
            self.scroll_direction = 0
            self.scroll_accumulator = 0.0
        
        # Process smooth scrolling
        if self.scroll_direction != 0:
            # dt is in milliseconds, convert to seconds
            dt_seconds = dt / 1000.0
            self.scroll_accumulator += dt_seconds
            
            # Scroll at scroll_rate lines per second
            lines_to_scroll = int(self.scroll_accumulator * self.scroll_rate)
            if lines_to_scroll > 0:
                visible_lines = self.renderer.char_height - 2
                max_scroll = max(0, len(self.output_lines) - visible_lines)
                
                if self.scroll_direction == -1:
                    # Scroll up (older content)
                    self.scroll_offset = min(max_scroll, self.scroll_offset + lines_to_scroll)
                else:
                    # Scroll down (newer content)
                    self.scroll_offset = max(0, self.scroll_offset - lines_to_scroll)
                
                # Keep remainder for next frame
                self.scroll_accumulator -= lines_to_scroll / self.scroll_rate
        
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
        
        # Check sudo timeout (just checks, doesn't show message)
        if self.sudo_authenticated:
            current_time = pygame.time.get_ticks()
            if current_time - self.sudo_timestamp > self.sudo_timeout:
                self.sudo_authenticated = False
    
    def complete_boot(self):
        """Complete the boot sequence and show main screen or intro"""
        self.booting = False
        self.output_lines = []
        
        # Check if we should prompt about existing save (built games only)
        if self.game.save_system.should_prompt_for_existing_save():
            # Show save prompt
            self.showing_save_prompt = True
            self.save_prompt_waiting_for_input = False
            self._show_save_prompt()
        # Check if intro should be shown
        elif not self.game.save_system.has_intro_been_shown():
            # Show intro sequence
            self.showing_intro = True
            self.intro_page = 0
            self.intro_waiting_for_key = False
            self._start_intro_page(0)
        else:
            # Skip intro, show main screen
            self._show_main_screen()
    
    def _show_save_prompt(self):
        """Show prompt asking if user wants to use existing save"""
        self.output_lines = []
        prompt_text = [
            "Existing save file detected.",
            "",
            "Would you like to continue from your previous save?",
            "",
            "Type 'yes' to load your existing save, or 'no' to start fresh.",
            "",
            "> "
        ]
        self.type_output(prompt_text, delay=15)
        self.save_prompt_waiting_for_input = True
    
    def _start_intro_page(self, page_index):
        """Start showing an intro page"""
        if page_index < len(self.intro_text_pages):
            self.intro_waiting_for_key = False
            # Clear output and start typing the page
            self.output_lines = []
            self.type_output(self.intro_text_pages[page_index], delay=15)
    
    def _show_main_screen(self):
        """Show the main screen (ASCII title and welcome)"""
        # Add ASCII title
        for line in BLTHLL_ASCII:
            self.output_lines.append(line)
        self.output_lines.append("")
        
        # Add welcome text
        for line in get_welcome_text():
            self.output_lines.append(line)
        
        # Track initial directory visit
        current_path = self.filesystem.get_pwd()
        self.game.save_system.mark_directory_visited(current_path)

    def _easter_egg_commands(self, cmd_lower, command):
        """
        Handle easter egg commands
        
        Args:
            cmd_lower: The lowercase command string
            command: The original command string
            
        Returns:
            True if command was handled, False otherwise
        """
        # Easter eggs!
        if cmd_lower in ["hello", "hi"]:
            self.add_output("Hello, human. Ready to dodge some bullets?")
            self.add_output("")
            return True
        
        elif cmd_lower == "whoami":
            current_user = self.filesystem.get_current_user()
            self.add_output(current_user)
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
        
        elif cmd_lower == "brew":
            # Homebrew-style help
            self.add_output("Example usage:")
            self.add_output("  brew search TEXT|/REGEX/")
            self.add_output("  brew info [FORMULA...]")
            self.add_output("  brew install FORMULA...")
            self.add_output("  brew update")
            self.add_output("  brew upgrade [FORMULA...]")
            self.add_output("  brew uninstall FORMULA...")
            self.add_output("  brew list [FORMULA...]")
            self.add_output("")
            self.add_output("Troubleshooting:")
            self.add_output("  brew config")
            self.add_output("  brew doctor")
            self.add_output("  brew install --verbose --debug FORMULA")
            self.add_output("")
            self.add_output("Further help:")
            self.add_output("  brew commands")
            self.add_output("  brew help [COMMAND]")
            self.add_output("")
            return True
        
        elif cmd_lower == "brew update":
            # Simulate brew update
            self.type_output([
                "==> Updating Homebrew...",
                "==> Downloading ghcr.io/v2/blthll/core/portable-tools/blobs/sha256:a7f3c9...",
                "######################################################################## 100.0%",
                "==> Pouring portable-tools-1.0.0.arm64_ventura.bottle.tar.gz",
                "",
                "==> Homebrew collects anonymous analytics.",
                "Read the analytics documentation (and how to opt-out) here:",
                "  https://docs.brew.sh/Analytics",
                "",
                "Updated 1 tap (blthll/core).",
                "==> New Formulae",
                "blthll-extras        emacs               radar-boost",
                "debug-mode           power-tools         secret-scanner",
                "time-warp",
                "",
                "You have packages available to install.",
                "You can install them with: brew install <formula>",
                ""
            ], delay=30)
            self._mark_secret_found("brew_update")
            return True
        
        elif cmd_lower.startswith("brew install "):
            # Extract package name
            package = command[13:].strip()
            if not package:
                self.add_output("Error: This command requires a formula argument")
                self.add_output("")
                return True
            
            # Check if this is a recognized package first
            if package == "emacs":
                # Simulate installation (all messages go through type_output for proper ordering)
                self.type_output([
                    f"==> Downloading {package}...",
                    "######################################################################## 100.0%",
                    f"==> Installing {package}",
                    f"==> Pouring {package}--1.0.0.arm64_ventura.bottle.tar.gz",
                    "",
                    "GNU Emacs text editor installed!",
                    "New command available: emacs <file>",
                ], delay=30)
                
                # Install package immediately (don't wait for typing)
                self.game.save_system.install_package("emacs")
                self._mark_secret_found("brew_emacs")
            else:
                self.add_output(f"Error: No available formula with the name \"{package}\"")
                self.add_output("Try: brew update")
            
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
            
            # Helper to format time
            def format_time(seconds):
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                secs = int(seconds % 60)
                if hours > 0:
                    return f"{hours}h {minutes}m {secs}s"
                elif minutes > 0:
                    return f"{minutes}m {secs}s"
                else:
                    return f"{secs}s"
            
            self.add_output("=== STATISTICS ===")
            self.add_output("")
            
            # Overall playtime
            total_playtime = stats.get('total_playtime_seconds', 0)
            if total_playtime > 0:
                self.add_output(f"Total Playtime: {format_time(total_playtime)}")
                self.add_output("")
            
            # Bullet Hell stats - only show if there are meaningful stats
            bullet_hell_time = stats.get('bullet_hell_playtime_seconds', 0)
            enemies_depleted = stats.get('enemies_depleted', 0)
            closest = stats.get('closest_call', 999)
            has_bullet_hell_stats = (total_games > 0 or total_time > 0 or bullet_hell_time > 0 or 
                                    enemies_depleted > 0 or closest < 999)
            
            if has_bullet_hell_stats:
                self.add_output("Bullet Hell:")
                if total_games > 0:
                    self.add_output(f"  Games Played: {total_games}")
                if total_time > 0:
                    self.add_output(f"  Total Time Survived: {total_time}s")
                if bullet_hell_time > 0:
                    self.add_output(f"  Total Playtime: {format_time(bullet_hell_time)}")
                if enemies_depleted > 0:
                    self.add_output(f"  Enemies Depleted: {enemies_depleted}")
                if closest < 999:
                    self.add_output(f"  Closest Call: {closest:.2f} tiles")
                self.add_output("")
            
            # Set Game stats - only show if there are games played
            set_games = stats.get('set_games_played', 0)
            if set_games > 0:
                self.add_output("Set Game:")
                set_wins = stats.get('set_games_won', 0)
                set_losses = stats.get('set_games_lost', 0)
                total_sets = stats.get('total_sets_found', 0)
                best_score = stats.get('best_set_score', 0)
                set_game_time = stats.get('set_game_playtime_seconds', 0)
                win_rate = (set_wins / set_games) * 100
                self.add_output(f"  Games Played: {set_games}")
                self.add_output(f"  Games Won: {set_wins} ({win_rate:.1f}%)")
                self.add_output(f"  Games Lost: {set_losses}")
                self.add_output(f"  Total Sets Found: {total_sets}")
                if best_score > 0:
                    self.add_output(f"  Best Score: {best_score} sets")
                if set_game_time > 0:
                    self.add_output(f"  Total Playtime: {format_time(set_game_time)}")
                self.add_output("")
            
            # Asteroids stats - only show if there are games played
            asteroids_games = stats.get('asteroids_games_played', 0)
            if asteroids_games > 0:
                self.add_output("Asteroids:")
                asteroids_best = stats.get('asteroids_best_score', 0)
                asteroids_total = stats.get('asteroids_total_score', 0)
                asteroids_stage = stats.get('asteroids_highest_stage', 0)
                asteroids_time = stats.get('asteroids_playtime_seconds', 0)
                self.add_output(f"  Games Played: {asteroids_games}")
                if asteroids_best > 0:
                    self.add_output(f"  Best Score: {asteroids_best:,}")
                if asteroids_total > 0:
                    avg_score = asteroids_total // asteroids_games
                    self.add_output(f"  Average Score: {avg_score:,}")
                if asteroids_stage > 0:
                    self.add_output(f"  Highest Stage: {asteroids_stage}")
                if asteroids_time > 0:
                    self.add_output(f"  Total Playtime: {format_time(asteroids_time)}")
                self.add_output("")
            
            # Oregon Trail stats
            oregon_time = stats.get('oregon_trail_playtime_seconds', 0)
            if oregon_time > 0:
                self.add_output("Oregon Trail:")
                self.add_output(f"  Total Playtime: {format_time(oregon_time)}")
                self.add_output("")
            
            self.add_output("Exploration:")
            self.add_output(f"  Secrets Found: {len(self.secret_commands_found)}")
            self.add_output(f"  Directories Visited: {exploration['dirs_visited']}")
            self.add_output(f"  Files Read: {exploration['files_read']}")
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
        
        # Save command history periodically (every 10 commands to avoid too many writes)
        if len(self.command_history) % 10 == 0:
            self.game.save_system.save_command_history(self.command_history)
        
        # Show command in output
        self.add_output(f"{self.get_prompt()}{command}")
        
        # Parse and execute
        cmd_lower = command.lower()
        
        # Handle sudo commands
        if cmd_lower.startswith("sudo "):
            self._handle_sudo_command(command[5:].strip())
            return
        
        if cmd_lower in ["start", "new", "newgame", "new game", "begin"]:
            self.add_output("Starting new game...")
            self.add_output("")
            # Launch gameplay state, passing this menu state to return to
            from src.states.games.gameplay import GameplayState
            self.game.change_state(GameplayState(self.game, previous_state=self))
        
        elif cmd_lower in ["continue", "load", "resume"]:
            self.add_output("Your progress is saved automatically. Type 'start' to play.")
            self.add_output("")
        
        elif cmd_lower in ["quit", "exit", "q"]:
            # Save command history before quitting
            self.game.save_system.save_command_history(self.command_history)
            self.add_output("Shutting down...")
            self.game.running = False
        
        elif cmd_lower in ["help", "?", "commands"]:
            for line in get_help_text():
                self.add_output(line)
                # After "  start       - Begin a new game", add unlocked game start options
                if line.strip().startswith("start") and "Begin a new game" in line:
                    for extra in get_unlocked_game_help_lines(self.game.save_system):
                        self.add_output(extra)
        
        elif cmd_lower in ["about", "info", "version"]:
            for line in get_about_text():
                self.add_output(line)
        
        elif cmd_lower in ["clear", "cls"]:
            self.output_lines = []
        
        elif cmd_lower.startswith("ls") and (cmd_lower == "ls" or cmd_lower == "dir" or cmd_lower[2:3] in (' ', '-')):
            # Parse ls arguments: flags and optional path
            rest = command[2:].strip() if len(command) > 2 else ""
            flags = ""
            ls_path = None
            # Split tokens to find flags vs path
            tokens = rest.split()
            for tok in tokens:
                if tok.startswith('-'):
                    flags += tok[1:]
                else:
                    ls_path = tok

            show_hidden = 'a' in flags
            show_long = 'l' in flags
            # Validate flags (only l and a are supported)
            unknown_flags = set(flags) - {'l', 'a'}
            if unknown_flags:
                self.add_output(f"ls: invalid option -- '{list(unknown_flags)[0]}'")
                self.add_output("")
                return

            # Get items from path or current directory
            if ls_path:
                success, result = self.filesystem.list_directory_at_path(ls_path, show_hidden=show_hidden)
                if not success:
                    self.add_output(result)
                    self.add_output("")
                    return
                items = result
            else:
                items = self.filesystem.list_directory(show_hidden=show_hidden)

            if show_long:
                # Prepend . and .. for -a
                if show_hidden:
                    current_user = self.filesystem.get_current_user()
                    self.add_output(f"drwxr-xr-x  {current_user:6}  ./")
                    self.add_output(f"drwxr-xr-x  {current_user:6}  ../")
                if items:
                    for item in items:
                        if item.endswith('/'):
                            owner = self.filesystem.get_file_owner(item)
                            self.add_output(f"drwxr-xr-x  {owner:6}  {item}")
                        else:
                            perms = self.filesystem.get_permissions(item)
                            owner = self.filesystem.get_file_owner(item)
                            if perms:
                                if len(perms) == 3:
                                    perms_display = perms + "------"
                                elif len(perms) == 9:
                                    perms_display = perms
                                else:
                                    perms_display = perms + "-" * (9 - len(perms))
                                self.add_output(f"-{perms_display}  {owner:6}  {item}")
                            else:
                                self.add_output(f"-rw-------  {owner:6}  {item}")
                elif not show_hidden:
                    self.add_output("(empty directory)")
            else:
                if items:
                    self._format_ls_output(items)
                else:
                    self.add_output("(empty directory)")
            self.add_output("")
            # Track directory visit
            current_path = self.filesystem.get_pwd()
            self.game.save_system.mark_directory_visited(current_path)
        
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
            else:
                # Track directory visit
                current_path = self.filesystem.get_pwd()
                self.game.save_system.mark_directory_visited(current_path)
        
        elif cmd_lower.startswith("man "):
            # Manual pages
            topic = command[4:].strip().lower()
            if topic == "python":
                self.add_output("PYTHON(1)                    BLTHLL Terminal Manual                    PYTHON(1)")
                self.add_output("")
                self.add_output("NAME")
                self.add_output("       python - Python scripting in BLTHLL Terminal")
                self.add_output("")
                self.add_output("DESCRIPTION")
                self.add_output("       Python scripts can be executed using 'python <file.py>' or 'run <file.py>'.")
                self.add_output("       Scripts run in a restricted environment with access to standard library functions.")
                self.add_output("")
                self.add_output("STANDARD LIBRARY")
                self.add_output("       File Operations:")
                self.add_output("         open(filename, mode='r')")
                self.add_output("           - Open a file using Python's standard open() function")
                self.add_output("           - Modes: 'r' (read), 'w' (write), 'a' (append), 'x' (exclusive)")
                self.add_output("           - Returns: File-like object (supports with statement)")
                self.add_output("           - Example: with open('file.txt', 'w') as f: f.write('text')")
                self.add_output("")
                self.add_output("       os Module:")
                self.add_output("         os.getcwd()")
                self.add_output("           - Get current working directory")
                self.add_output("           - Returns: str (e.g., '/home/pilot/blthll')")
                self.add_output("")
                self.add_output("         os.listdir()")
                self.add_output("           - List files in current directory")
                self.add_output("           - Returns: List of filenames and directories")
                self.add_output("")
                self.add_output("         os.stat(path)")
                self.add_output("           - Get file statistics")
                self.add_output("           - Returns: stat_result object with:")
                self.add_output("             * st_size: file size in bytes")
                self.add_output("             * st_mode: permission string (e.g., 'rwxrwxrwx')")
                self.add_output("             * st_uid: file owner ('pilot' or 'root')")
                self.add_output("           - Raises FileNotFoundError if file doesn't exist")
                self.add_output("")
                self.add_output("         os.access(path, mode)")
                self.add_output("           - Check file access permissions")
                self.add_output("           - Modes: os.F_OK (existence), os.R_OK (read), os.W_OK (write), os.X_OK (execute)")
                self.add_output("           - Returns: True or False")
                self.add_output("")
                self.add_output("         os.remove(path) / os.unlink(path)")
                self.add_output("           - Delete a file")
                self.add_output("           - Raises FileNotFoundError if file doesn't exist")
                self.add_output("")
                self.add_output("       os.path Module:")
                self.add_output("         os.path.exists(path)")
                self.add_output("           - Check if path exists")
                self.add_output("           - Returns: True or False")
                self.add_output("")
                self.add_output("         os.path.getsize(path)")
                self.add_output("           - Get file size in bytes")
                self.add_output("           - Returns: int (bytes)")
                self.add_output("           - Raises FileNotFoundError if file doesn't exist")
                self.add_output("")
                self.add_output("         os.path.isfile(path)")
                self.add_output("           - Check if path is a file")
                self.add_output("           - Returns: True or False")
                self.add_output("")
                self.add_output("         os.path.isdir(path)")
                self.add_output("           - Check if path is a directory")
                self.add_output("           - Returns: True or False")
                self.add_output("")
                self.add_output("EXAMPLES")
                self.add_output("       # Check if a file is exactly 16 bits")
                self.add_output("       if os.path.exists('.node_1'):")
                self.add_output("           size = os.path.getsize('.node_1')")
                self.add_output("           if size * 8 == 16:")
                self.add_output("               print('Found the 16-bit node!')")
                self.add_output("")
                self.add_output("       # List all files in current directory")
                self.add_output("       files = os.listdir()")
                self.add_output("       for f in files:")
                self.add_output("           print(f)")
                self.add_output("")
                self.add_output("       # Read and process a file")
                self.add_output("       with open('data.txt', 'r') as f:")
                self.add_output("           for line in f:")
                self.add_output("               print(line.strip().upper())")
                self.add_output("")
                self.add_output("       # Delete files over 16 bits")
                self.add_output("       files = os.listdir()")
                self.add_output("       for f in files:")
                self.add_output("           if os.path.isfile(f):")
                self.add_output("               size = os.path.getsize(f)")
                self.add_output("               if size * 8 > 16:")
                self.add_output("                   os.remove(f)")
                self.add_output("                   print(f'Deleted: {f}')")
                self.add_output("")
                self.add_output("       # Using Python's open() function")
                self.add_output("       with open('output.txt', 'w') as f:")
                self.add_output("           f.write('Hello, World!\\n')")
                self.add_output("           f.write('This is line 2\\n')")
                self.add_output("")
                self.add_output("       # Reading with open()")
                self.add_output("       with open('output.txt', 'r') as f:")
                self.add_output("           content = f.read()")
                self.add_output("           print(content)")
                self.add_output("")
                self.add_output("       # Appending to a file")
                self.add_output("       with open('log.txt', 'a') as f:")
                self.add_output("           f.write('New log entry\\n')")
                self.add_output("")
                self.add_output("       # Check file permissions")
                self.add_output("       if os.access('file.txt', os.R_OK):")
                self.add_output("           print('File is readable')")
                self.add_output("")
                self.add_output("       # Get file statistics")
                self.add_output("       try:")
                self.add_output("           stat_info = os.stat('file.txt')")
                self.add_output("           print(f'Size: {stat_info.st_size} bytes')")
                self.add_output("           print(f'Permissions: {stat_info.st_mode}')")
                self.add_output("           print(f'Owner: {stat_info.st_uid}')")
                self.add_output("       except FileNotFoundError:")
                self.add_output("           print('File not found')")
                self.add_output("")
                self.add_output("       # Create a new file")
                self.add_output("       with open('new_file.txt', 'w') as f:")
                self.add_output("           f.write('Hello')")
                self.add_output("           print('File created!')")
                self.add_output("")
                self.add_output("RESTRICTIONS")
                self.add_output("       - Scripts have a 5 second execution time limit")
                self.add_output("       - Only 'os' and 'os.path' modules are available")
                self.add_output("       - Import statements are restricted")
                self.add_output("       - Dangerous builtins (exec, eval, compile) are disabled")
                self.add_output("")
                self.add_output("SEE ALSO")
                self.add_output("       help(1)")
                self.add_output("")
            elif topic in self._get_man_pages():
                for line in self._get_man_pages()[topic]:
                    self.add_output(line)
                self.add_output("")
            else:
                self.add_output(f"No manual entry for '{topic}'")
                available = ", ".join(sorted(["python"] + list(self._get_man_pages().keys())))
                self.add_output(f"Available manual pages: {available}")
                self.add_output("")
        
        elif cmd_lower.startswith("readme ") or cmd_lower == "readme":
            # View markdown README file with formatting
            if cmd_lower == "readme":
                # Try common README filenames
                readme_names = ["README.md", "README", "readme.md", "readme"]
                filename = None
                for name in readme_names:
                    success, _ = self.filesystem.read_file(name)
                    if success:
                        filename = name
                        break
                if not filename:
                    self.add_output("Error: No README file found. Try 'readme <filename>'")
                    self.add_output("")
            else:
                filename = command[7:].strip()
            
            if filename:
                # Launch README viewer
                from src.states.unix_utils.readme_viewer import ReadmeViewerState
                readme_state = ReadmeViewerState(self.game, self.filesystem, filename, self)
                self.game.change_state(readme_state)
                # Track file read
                current_path = self.filesystem.get_pwd()
                self.game.save_system.mark_file_read(f"{current_path}/{filename}")
        
        elif cmd_lower.startswith("cat "):
            # Read file (supports relative/absolute paths)
            filename = command[4:].strip()
            # Check if target is a directory
            if self.filesystem.is_directory(filename):
                self.add_output(f"cat: {filename}: Is a directory")
                self.add_output("")
            else:
                # Use path-aware read if path contains /
                if '/' in filename:
                    success, content = self.filesystem.read_file_at_path(filename)
                else:
                    success, content = self.filesystem.read_file(filename)
                if success:
                    for line in content:
                        self.add_output(str(line))
                    self.add_output("")
                    # Track file read
                    current_path = self.filesystem.get_pwd()
                    self.game.save_system.mark_file_read(f"{current_path}/{filename}")
                else:
                    self.add_output(content)
                    self.add_output("")
        
        elif cmd_lower.startswith("stat "):
            # Show file statistics
            filename = command[5:].strip()
            if not filename:
                self.add_output("stat: missing file operand")
                self.add_output("Usage: stat <filename>")
                self.add_output("")
                return
            
            # Check if it's a directory first
            current_dir = self.filesystem.get_current_directory()
            is_dir = False
            dir_name = filename.rstrip('/')
            dir_path_for_timestamp = self.filesystem.get_pwd() + '/' + dir_name
            if 'dirs' in current_dir and dir_name in current_dir['dirs']:
                is_dir = True
            else:
                # Check user-created directories
                current_path = self.filesystem.get_pwd()
                dir_path = f"{current_path}/{dir_name}/"
                if dir_path in self.filesystem.user_created_dirs:
                    is_dir = True
            
            # Check if file/directory exists
            if is_dir:
                # Directory exists
                size = 0
                # Update access time for directory (stat updates access time)
                self.filesystem._update_timestamp(dir_path_for_timestamp, 'access')
            elif self.filesystem.file_exists(filename):
                # File exists - get its size
                success, content = self.filesystem.read_file(filename)
                if success:
                    if isinstance(content, list):
                        # Calculate size: each line's length + newlines between lines (not after last)
                        # Convert to string to handle non-string content (e.g., integers)
                        if len(content) == 0:
                            size = 0
                        elif len(content) == 1:
                            # Single line - no newline needed for 1-byte files
                            size = len(str(content[0]))
                        else:
                            # Multiple lines: sum of line lengths + newlines between them
                            size = sum(len(str(line)) for line in content) + (len(content) - 1)
                    else:
                        # Single string content (or other type - convert to string)
                        size = len(str(content))
                else:
                    # Permission denied - still show stat but with size 0
                    size = 0
            else:
                self.add_output(f"stat: cannot stat '{filename}': No such file or directory")
                self.add_output("")
                return
            
            # Get permissions
            perms = self.filesystem.get_permissions(filename)
            if not perms:
                perms = "rwxrwxrwx"
            
            # Get owner
            owner = self.filesystem.get_file_owner(filename)
            
            # Determine file type
            file_type = "directory" if is_dir else "regular file"
            
            # Format permissions for display
            if len(perms) == 3:
                perms_display = perms + "------"
            elif len(perms) == 9:
                perms_display = perms
            else:
                perms_display = perms + "-" * (9 - len(perms))
            
            # Get timestamps
            if is_dir:
                full_path = dir_path_for_timestamp
            else:
                full_path = self.filesystem.get_pwd() + '/' + filename
            access_time = self.filesystem._get_timestamp(full_path, 'access')
            modify_time = self.filesystem._get_timestamp(full_path, 'modify')
            change_time = self.filesystem._get_timestamp(full_path, 'change')
            
            # Format timestamps (convert ISO to Unix stat format)
            from datetime import datetime
            try:
                access_dt = datetime.fromisoformat(access_time)
                modify_dt = datetime.fromisoformat(modify_time)
                change_dt = datetime.fromisoformat(change_time)
                access_str = access_dt.strftime("%Y-%m-%d %H:%M:%S.%f")
                modify_str = modify_dt.strftime("%Y-%m-%d %H:%M:%S.%f")
                change_str = change_dt.strftime("%Y-%m-%d %H:%M:%S.%f")
            except (ValueError, AttributeError):
                # Fallback if timestamp format is unexpected
                access_str = access_time
                modify_str = modify_time
                change_str = change_time
            
            # Calculate blocks (512-byte blocks, rounded up)
            blocks = (size + 511) // 512 if size > 0 else 0
            
            # Display stat information (similar to Unix stat command)
            self.add_output(f"  File: {filename}")
            self.add_output(f"  Size: {size:<12} Blocks: {blocks:<10} IO Block: 4096   {file_type}")
            inode = abs(hash(full_path)) % 999999 + 1000
            self.add_output(f"Device: 801h/{2049:<8} Inode: {inode:<6} Links: 1")
            self.add_output(f"Access: ({perms_display})  Uid: ({owner})   Gid: (users)")
            self.add_output(f"Access: {access_str}")
            self.add_output(f"Modify: {modify_str}")
            self.add_output(f"Change: {change_str}")
            self.add_output("")

        elif cmd_lower.startswith("head "):
            # Show first N lines of a file
            args = command[5:].strip().split()
            num_lines = 10
            filename = None
            i = 0
            while i < len(args):
                if args[i] == '-n' and i + 1 < len(args):
                    try:
                        num_lines = int(args[i + 1])
                    except ValueError:
                        pass
                    i += 2
                elif args[i].startswith('-') and args[i][1:].isdigit():
                    num_lines = int(args[i][1:])
                    i += 1
                else:
                    filename = args[i]
                    i += 1
            if not filename:
                self.add_output("head: missing file operand")
                self.add_output("Usage: head [-n N] <file>")
                self.add_output("")
            else:
                if '/' in filename:
                    success, content = self.filesystem.read_file_at_path(filename)
                else:
                    success, content = self.filesystem.read_file(filename)
                if success:
                    for line in content[:num_lines]:
                        self.add_output(str(line))
                else:
                    self.add_output(f"head: {content}")
                self.add_output("")

        elif cmd_lower.startswith("tail "):
            # Show last N lines of a file
            args = command[5:].strip().split()
            num_lines = 10
            filename = None
            i = 0
            while i < len(args):
                if args[i] == '-n' and i + 1 < len(args):
                    try:
                        num_lines = int(args[i + 1])
                    except ValueError:
                        pass
                    i += 2
                elif args[i].startswith('-') and args[i][1:].isdigit():
                    num_lines = int(args[i][1:])
                    i += 1
                else:
                    filename = args[i]
                    i += 1
            if not filename:
                self.add_output("tail: missing file operand")
                self.add_output("Usage: tail [-n N] <file>")
                self.add_output("")
            else:
                if '/' in filename:
                    success, content = self.filesystem.read_file_at_path(filename)
                else:
                    success, content = self.filesystem.read_file(filename)
                if success:
                    for line in content[-num_lines:]:
                        self.add_output(str(line))
                else:
                    self.add_output(f"tail: {content}")
                self.add_output("")

        elif cmd_lower.startswith("grep "):
            # Search for pattern in file(s)
            args = command[5:].strip()
            if not args:
                self.add_output("grep: missing pattern")
                self.add_output("Usage: grep <pattern> <file>")
                self.add_output("")
            else:
                # Parse: grep [-i] [-n] pattern file
                tokens = args.split()
                case_insensitive = False
                show_line_nums = False
                while tokens and tokens[0].startswith('-'):
                    flag = tokens.pop(0)
                    if 'i' in flag:
                        case_insensitive = True
                    if 'n' in flag:
                        show_line_nums = True
                if len(tokens) < 2:
                    self.add_output("grep: missing pattern or file")
                    self.add_output("Usage: grep [-i] [-n] <pattern> <file>")
                    self.add_output("")
                else:
                    pattern = tokens[0].strip("'\"")
                    filename = tokens[1]
                    if '/' in filename:
                        success, content = self.filesystem.read_file_at_path(filename)
                    else:
                        success, content = self.filesystem.read_file(filename)
                    if success:
                        found = False
                        for i, line in enumerate(content, 1):
                            line_str = str(line)
                            match = (pattern.lower() in line_str.lower()) if case_insensitive else (pattern in line_str)
                            if match:
                                found = True
                                if show_line_nums:
                                    self.add_output(f"{i}:{line_str}")
                                else:
                                    self.add_output(line_str)
                        if not found:
                            pass  # grep returns empty on no match (standard behavior)
                    else:
                        self.add_output(f"grep: {filename}: No such file or directory")
                    self.add_output("")

        elif cmd_lower.startswith("wc "):
            # Word/line/char count
            filename = command[3:].strip()
            # Strip common flags (just ignore them, show all counts)
            if filename.startswith('-'):
                parts = filename.split(None, 1)
                filename = parts[1] if len(parts) > 1 else ""
            if not filename:
                self.add_output("wc: missing file operand")
                self.add_output("Usage: wc <file>")
                self.add_output("")
            else:
                if '/' in filename:
                    success, content = self.filesystem.read_file_at_path(filename)
                else:
                    success, content = self.filesystem.read_file(filename)
                if success:
                    lines = len(content)
                    words = sum(len(str(line).split()) for line in content)
                    chars = sum(len(str(line)) for line in content) + max(0, lines - 1)  # newlines
                    self.add_output(f"  {lines:6}  {words:6}  {chars:6} {filename}")
                else:
                    self.add_output(f"wc: {filename}: No such file or directory")
                self.add_output("")

        elif cmd_lower.startswith("file "):
            # Identify file type
            name = command[5:].strip()
            if not name:
                self.add_output("file: missing file operand")
                self.add_output("")
            elif self.filesystem.is_directory(name):
                self.add_output(f"{name}: directory")
                self.add_output("")
            elif self.filesystem.file_exists(name):
                ext = name.rsplit('.', 1)[-1] if '.' in name else ''
                type_map = {
                    'py': 'Python script, ASCII text executable',
                    'txt': 'ASCII text',
                    'md': 'UTF-8 Unicode text, markdown',
                    'dat': 'data',
                    'log': 'ASCII text, log file',
                    'conf': 'ASCII text, configuration file',
                    'service': 'systemd unit file, ASCII text',
                    'sh': 'Bourne-Again shell script, ASCII text executable',
                    'json': 'JSON data, ASCII text',
                }
                file_type = type_map.get(ext, 'ASCII text')
                # Check if file starts with shebang
                success, content = self.filesystem.read_file(name)
                if success and content and str(content[0]).startswith('#!'):
                    file_type = f"script, {file_type}"
                if name.startswith('.'):
                    file_type = f"hidden file, {file_type}"
                self.add_output(f"{name}: {file_type}")
                self.add_output("")
            else:
                self.add_output(f"file: {name}: No such file or directory")
                self.add_output("")

        elif cmd_lower == "find" or cmd_lower.startswith("find "):
            # Simplified find command
            args = command[5:].strip() if len(command) > 5 else ""
            tokens = args.split() if args else []
            search_path = "."
            name_pattern = None

            # Parse arguments
            i = 0
            while i < len(tokens):
                if tokens[i] == '-name' and i + 1 < len(tokens):
                    name_pattern = tokens[i + 1].strip("'\"")
                    i += 2
                elif tokens[i] == '-type':
                    i += 2  # Skip -type flag (ignore it)
                elif not tokens[i].startswith('-'):
                    search_path = tokens[i]
                    i += 1
                else:
                    i += 1

            # Walk the filesystem
            import fnmatch
            found_any = False
            for dirpath, dirnames, filenames in self.filesystem.walk_directory(search_path if search_path != "." else None):
                # Make paths relative to search_path
                if search_path == ".":
                    rel = dirpath[len(self.filesystem.get_pwd()):]
                    display_path = "." + rel if rel else "."
                else:
                    display_path = dirpath

                for d in dirnames:
                    full_display = display_path.rstrip('/') + '/' + d
                    if name_pattern is None or fnmatch.fnmatch(d, name_pattern):
                        self.add_output(full_display)
                        found_any = True
                for f in filenames:
                    full_display = display_path.rstrip('/') + '/' + f
                    if name_pattern is None or fnmatch.fnmatch(f, name_pattern):
                        self.add_output(full_display)
                        found_any = True

            if not found_any and name_pattern:
                pass  # find returns empty on no matches
            self.add_output("")

        elif cmd_lower.startswith("cp "):
            # Copy file
            args = command[3:].strip().split()
            if len(args) == 2:
                source, destination = args
                success, error = self.filesystem.copy_file(source, destination)
                if success:
                    self.add_output(f"Copied: {source} -> {destination}")
                    self._save_filesystem()
                else:
                    self.add_output(error)
            else:
                self.add_output("Usage: cp <source> <destination>")
            self.add_output("")

        elif cmd_lower.startswith("touch "):
            # Create empty file
            filename = command[6:].strip()
            success, error = self.filesystem.create_file(filename)
            if success:
                self.add_output(f"Created file: {filename}")
                self._save_filesystem()
                # Check puzzle triggers after file creation (might create override files)
                full_touch_path = self.filesystem.get_pwd() + '/' + filename
                if '/etc/systemd/system/' in full_touch_path:
                    for _game, msg in self._check_puzzle_triggers("systemctl"):
                        self.add_output("")
                        self.add_output(msg)
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
                # Check puzzle triggers after directory creation (might create override directories)
                full_mkdir_path = self.filesystem.get_pwd() + '/' + dirname
                if '/etc/systemd/system/' in full_mkdir_path:
                    for _game, msg in self._check_puzzle_triggers("systemctl"):
                        self.add_output("")
                        self.add_output(msg)
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
        
        elif cmd_lower == "rm save --filesystem":
            # Reset only filesystem
            self.add_output("Resetting filesystem to defaults...")
            self.add_output("")
            self.game.save_system.reset_filesystem()
            self.filesystem.reset_to_defaults()
            self.add_output("Filesystem reset! Stats and other data preserved.")
            self.add_output("")
        
        elif cmd_lower == "rm save --stats":
            # Reset only game statistics
            self.add_output("Resetting game statistics...")
            self.add_output("")
            self.game.save_system.reset_stats()
            self.add_output("Statistics reset! Filesystem and other data preserved.")
            self.add_output("")
        
        elif cmd_lower == "rm save --filesystem-keep-files":
            # Reset filesystem but keep user-created files
            self.add_output("Resetting filesystem (preserving your files)...")
            self.add_output("")
            self.game.save_system.reset_filesystem()
            self.filesystem.reset_filesystem_keep_user_files()
            self.add_output("Filesystem reset! Your custom files have been moved to blthll/")
            self.add_output("")
        
        elif cmd_lower.startswith("rm save --dir "):
            # Reset a specific directory to default state
            dir_path = command[15:].strip()  # "rm save --dir " is 15 chars
            if not dir_path:
                self.add_output("Usage: rm save --dir <directory>")
                self.add_output("")
            else:
                success, error = self.filesystem.reset_directory(dir_path)
                if success:
                    self.add_output(f"Directory '{dir_path}' reset to default state.")
                    self.add_output("  - Removed user-created files")
                    self.add_output("  - Moved default files back to original locations")
                    self.add_output("  - Restored deleted default files")
                    self._save_filesystem()
                else:
                    self.add_output(f"Error: {error}")
                self.add_output("")
        
        elif cmd_lower.startswith("rm -r ") or cmd_lower.startswith("rm -rf ") or cmd_lower.startswith("rm -fr "):
            # Recursive directory delete (only for user-created directories)
            # Extract dirname after flags
            parts = command.split(None, 2)
            if len(parts) < 3:
                self.add_output("rm: missing operand")
                self.add_output("")
            else:
                dirname = parts[2].strip()
                if dirname in ['/', '/home', '/usr', '/etc', '/var', '/bin', '/system']:
                    self.add_output("ERROR: Cannot delete bullets. They multiply too fast!")
                    self.add_output("")
                    self._mark_secret_found("destructive")
                else:
                    success, error = self.filesystem.delete_directory_recursive(dirname)
                    if success:
                        self.add_output(f"Deleted: {dirname}/")
                        self._save_filesystem()
                    else:
                        self.add_output(error)
                    self.add_output("")

        elif cmd_lower.startswith("rm ") and not cmd_lower.startswith("rm -"):
            # Delete file
            filename = command[3:].strip()
            success, error = self.filesystem.delete_file(filename)
            if success:
                self.add_output(f"Deleted: {filename}")
                self._save_filesystem()
                # Check puzzle triggers that depend on rm
                for _game, msg in self._check_puzzle_triggers("rm"):
                    self.add_output("")
                    self.add_output(msg)
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
        
        elif cmd_lower.startswith("chmod "):
            # Change file permissions
            args = command[6:].strip().split()
            if len(args) == 2:
                permissions, filename = args
                success, error = self.filesystem.set_permissions(filename, permissions)
                if success:
                    self._save_filesystem()
                    # Check puzzle triggers that depend on chmod
                    for _game, msg in self._check_puzzle_triggers("chmod"):
                        self.add_output("")
                        self.add_output(msg)
                else:
                    self.add_output(error)
            else:
                self.add_output("Usage: chmod <mode> <filename>")
                self.add_output("Examples:")
                self.add_output("  chmod 755 script.py   # rwx (read, write, execute)")
                self.add_output("  chmod 644 data.txt    # rw- (read, write)")
                self.add_output("  chmod 444 readonly.txt # r-- (read only)")
            self.add_output("")
        
        elif cmd_lower.startswith("vim ") or cmd_lower.startswith("vi ") or cmd_lower.startswith("edit "):
            # Open text editor
            parts = command.split(None, 1)
            if len(parts) < 2:
                self.add_output("Usage: vim <filename>  or  vi <filename>  or  edit <filename>")
                self.add_output("")
            else:
                filename = parts[1].strip()
                try:
                    # Switch to editor state
                    from src.states.unix_utils.editor import EditorState
                    editor = EditorState(self.game, self.filesystem, filename, self)
                    self.game.change_state(editor)
                except Exception as e:
                    self.add_output(f"Error opening editor: {e}")
                    self.add_output("")
        
        elif cmd_lower == "emacs" or cmd_lower.startswith("emacs "):
            # Open emacs editor (requires brew install first)
            if not self.game.save_system.is_package_installed("emacs"):
                self.add_output("emacs: command not found")
                self.add_output("")
            else:
                parts = command.split(None, 1)
                if len(parts) < 2:
                    self.add_output("Usage: emacs <filename>")
                    self.add_output("")
                else:
                    filename = parts[1].strip()
                    try:
                        # Switch to editor state (same as vim)
                        from src.states.unix_utils.editor import EditorState
                        editor = EditorState(self.game, self.filesystem, filename, self, editor_name="emacs")
                        self.game.change_state(editor)
                    except Exception as e:
                        self.add_output(f"Error opening editor: {e}")
                        self.add_output("")
        
        elif cmd_lower == "code":
            # Open VSCode-like editor
            try:
                from src.states.unix_utils.vscode_editor import VSCodeEditorState
                editor = VSCodeEditorState(self.game, self.filesystem, self)
                self.game.change_state(editor)
            except Exception as e:
                self.add_output(f"Error opening editor: {e}")
                self.add_output("")
        
        elif cmd_lower.startswith("python ") or cmd_lower.startswith("run "):
            # Execute Python script
            filename = command.split(None, 1)[1].strip() if len(command.split(None, 1)) > 1 else ""
            if not filename:
                self.add_output("Usage: python <script.py>  or  run <script.py>")
                self.add_output("")
            elif not filename.endswith('.py'):
                self.add_output("Error: Only .py files can be executed")
                self.add_output("")
            else:
                # Check execute permission first
                if not self.filesystem.check_permission(filename, 'x'):
                    self.add_output(f"Permission denied: '{filename}'")
                    self.add_output("")
                else:
                    success, content = self.filesystem.read_file(filename)
                    if not success:
                        self.add_output(content)  # Error message
                        self.add_output("")
                    else:
                        self.add_output(f"Executing {filename}...")
                        self.add_output("")
                        
                        # Add process for the script
                        pid = self.process_manager.add_process(f"python {filename}", cpu_usage=2.5, mem_usage=5.0)
                        
                        # Import and use script executor
                        from src.unix.script_executor import ScriptExecutor
                        executor = ScriptExecutor()
                        
                        # Execute with output callback and save callback
                        exec_success, error = executor.execute(
                            content, 
                            self.filesystem, 
                            self.add_output,
                            self._save_filesystem
                        )
                        
                        # Remove process after execution
                        self.process_manager.remove_process(pid)
                        
                        if not exec_success:
                            self.add_output("")
                            self.add_output(f"Execution failed: {error}")
                        
                        self.add_output("")
                        self._mark_secret_found("script_runner")
        
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
                    # Check puzzle triggers after file write (might create override files)
                    # Only check systemctl puzzle if writing to systemd override directory
                    full_write_path = self.filesystem.get_pwd() + '/' + filename
                    if '/etc/systemd/system/' in full_write_path:
                        for _game, msg in self._check_puzzle_triggers("systemctl"):
                            self.add_output("")
                            self.add_output(msg)
                else:
                    self.add_output(error)
                self.add_output("")
            else:
                self.add_output("Invalid syntax. Use: echo text > file  or  echo text >> file")
                self.add_output("")
        
        elif cmd_lower.startswith("echo ") or cmd_lower == "echo":
            # Echo text to terminal (without redirect)
            text = command[5:].strip() if len(command) > 5 else ""
            # Strip surrounding quotes
            if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
                text = text[1:-1]
            self.add_output(text)
            self.add_output("")

        elif cmd_lower == "sudo":
            # sudo with no arguments
            self.add_output("usage: sudo <command>")
            self.add_output("")
        
        elif cmd_lower == "start spacebullets":
            # Launch Galaga game (only if virus was killed)
            if self.game.save_system.is_virus_killed():
                from src.states.games.galaga_gameplay import GalagaGameplayState
                galaga_state = GalagaGameplayState(self.game, self)
                self.game.change_state(galaga_state)
                self._mark_secret_found("arcade_master")
            else:
                self.add_output("start: 'spacebullets' - command not found")
                self.add_output("")
        
        elif cmd_lower == "start set":
            # Launch Set card game (only if unlocked via puzzle)
            if not self.game.save_system.is_game_unlocked("set"):
                return  # do nothing when locked
            from src.states.games.set_game import SetGameState
            set_state = SetGameState(self.game, self)
            self.game.change_state(set_state)
            self._mark_secret_found("set_player")
        
        elif cmd_lower == "start oregon" or cmd_lower == "start oregon_trail":
            # Launch Oregon Trail game (only if unlocked via puzzle)
            if not self.game.save_system.is_game_unlocked("oregon_trail"):
                return  # do nothing when locked
            try:
                from src.states.games.oregon_trail import OregonTrailState
                oregon_state = OregonTrailState(self.game, self)
                self.game.change_state(oregon_state)
                self._mark_secret_found("oregon_trail")
            except Exception as e:
                self.add_output(f"start: 'oregon_trail' - error: {e}")
                self.add_output("")
        
        elif cmd_lower == "start minesweeper":
            # Launch Minesweeper game (only if unlocked via puzzle)
            if not self.game.save_system.is_game_unlocked("minesweeper"):
                return  # do nothing when locked
            try:
                from src.states.games.minesweeper import MinesweeperState
                minesweeper_state = MinesweeperState(self.game, self)
                self.game.change_state(minesweeper_state)
                self._mark_secret_found("minesweeper")
            except Exception as e:
                self.add_output(f"start: 'minesweeper' - error: {e}")
                self.add_output("")
        
        elif cmd_lower in ["top", "htop"]:
            # Interactive process viewer
            from src.states.unix_utils.top_viewer import TopViewerState
            top_state = TopViewerState(self.game, self.process_manager, self)
            self.game.change_state(top_state)
            self._mark_secret_found("process_viewer")
        
        elif cmd_lower == "ps" or cmd_lower.startswith("ps "):
            # Static process list (ignore flags like aux, -ef, -e, -a)
            self._show_processes()

        elif cmd_lower.startswith("kill "):
            # Kill a process (tolerates signal flags like -9, -SIGKILL, -TERM)
            args = command[5:].strip().split()
            pid_str = None
            for arg in args:
                if arg.startswith('-'):
                    continue  # Skip signal flags
                pid_str = arg
                break
            if not pid_str:
                self.add_output("kill: missing process id")
                self.add_output("Usage: kill [-signal] <pid>")
                self.add_output("")
            else:
                try:
                    pid = int(pid_str)
                    self._kill_process(pid)
                except ValueError:
                    self.add_output(f"kill: invalid process id: {pid_str}")
                    self.add_output("")
        
        elif cmd_lower.startswith("systemctl ") or cmd_lower == "systemctl":
            # Check if systemctl is "installed" (Stage 1 of puzzle)
            if not self._is_systemctl_available():
                self.add_output("bash: systemctl: command not found")
                self.add_output("")
                return
            
            # Systemd control command
            if cmd_lower == "systemctl":
                self.add_output("systemctl: missing command")
                self.add_output("Usage: systemctl <command> [service]")
                self.add_output("Commands: status, start, stop, enable, disable, list-units, list-unit-files")
                self.add_output("")
                return
            
            args = command[10:].strip().split()
            if not args:
                self.add_output("systemctl: missing command")
                self.add_output("Usage: systemctl <command> [service]")
                self.add_output("Commands: status, start, stop, enable, disable, list-units, list-unit-files")
                self.add_output("")
            else:
                subcommand = args[0].lower()
                service_name = args[1] if len(args) > 1 else None
                
                if subcommand == "status":
                    if not service_name:
                        self.add_output("systemctl status: missing service name")
                        self.add_output("Usage: systemctl status <service>")
                        self.add_output("")
                    else:
                        self._systemctl_status(service_name)
                
                elif subcommand == "start":
                    if not service_name:
                        self.add_output("systemctl start: missing service name")
                        self.add_output("Usage: systemctl start <service>")
                        self.add_output("")
                    else:
                        self._systemctl_start(service_name)
                
                elif subcommand == "stop":
                    if not service_name:
                        self.add_output("systemctl stop: missing service name")
                        self.add_output("Usage: systemctl stop <service>")
                        self.add_output("")
                    else:
                        self._systemctl_stop(service_name)
                
                elif subcommand == "enable":
                    if not service_name:
                        self.add_output("systemctl enable: missing service name")
                        self.add_output("Usage: systemctl enable <service>")
                        self.add_output("")
                    else:
                        self._systemctl_enable(service_name)
                
                elif subcommand == "disable":
                    if not service_name:
                        self.add_output("systemctl disable: missing service name")
                        self.add_output("Usage: systemctl disable <service>")
                        self.add_output("")
                    else:
                        self._systemctl_disable(service_name)
                
                elif subcommand == "list-units":
                    self._systemctl_list_units()
                
                elif subcommand == "list-unit-files":
                    self._systemctl_list_unit_files()
                
                else:
                    self.add_output(f"systemctl: unknown command '{subcommand}'")
                    self.add_output("Usage: systemctl <command> [service]")
                    self.add_output("Commands: status, start, stop, enable, disable, list-units, list-unit-files")
                    self.add_output("")
        
        elif cmd_lower == "history":
            # Show command history
            for i, cmd in enumerate(self.command_history, 1):
                self.add_output(f"  {i:4}  {cmd}")
            self.add_output("")

        elif cmd_lower.startswith("which ") or cmd_lower.startswith("type "):
            # Show command location
            cmd_name = command.split(None, 1)[1].strip() if len(command.split(None, 1)) > 1 else ""
            command_paths = {
                'ls': '/usr/bin/ls', 'cd': '(shell builtin)', 'pwd': '/usr/bin/pwd',
                'cat': '/usr/bin/cat', 'head': '/usr/bin/head', 'tail': '/usr/bin/tail',
                'grep': '/usr/bin/grep', 'find': '/usr/bin/find', 'wc': '/usr/bin/wc',
                'cp': '/usr/bin/cp', 'mv': '/usr/bin/mv', 'rm': '/usr/bin/rm',
                'mkdir': '/usr/bin/mkdir', 'rmdir': '/usr/bin/rmdir',
                'touch': '/usr/bin/touch', 'chmod': '/usr/bin/chmod', 'stat': '/usr/bin/stat',
                'vim': '/usr/bin/vim', 'vi': '/usr/bin/vi', 'edit': '/usr/bin/edit',
                'python': '/usr/bin/python3', 'echo': '(shell builtin)',
                'kill': '/usr/bin/kill', 'ps': '/usr/bin/ps', 'top': '/usr/bin/top',
                'sudo': '/usr/bin/sudo', 'man': '/usr/bin/man', 'file': '/usr/bin/file',
                'uname': '/usr/bin/uname', 'hostname': '/usr/bin/hostname',
                'date': '/usr/bin/date', 'uptime': '/usr/bin/uptime',
                'id': '/usr/bin/id', 'whoami': '/usr/bin/whoami',
                'env': '/usr/bin/env', 'printenv': '/usr/bin/printenv',
                'history': '(shell builtin)', 'which': '/usr/bin/which',
                'type': '(shell builtin)', 'code': '/usr/bin/code',
            }
            # Check if systemctl is installed
            if cmd_name == 'systemctl' and self._is_systemctl_available():
                command_paths['systemctl'] = '/bin/systemctl'
            if cmd_name in command_paths:
                self.add_output(command_paths[cmd_name])
            else:
                self.add_output(f"{cmd_name}: not found")
            self.add_output("")

        elif cmd_lower == "uname -a" or cmd_lower == "uname --all":
            self.add_output("BLTHLL blthll-terminal 1.0.0 WalnutIndustries arm64 GNU/Linux")
            self.add_output("")

        elif cmd_lower == "uname" or cmd_lower.startswith("uname "):
            # uname with any other flags just shows the kernel name
            self.add_output("BLTHLL")
            self.add_output("")

        elif cmd_lower == "hostname":
            self.add_output("blthll-terminal")
            self.add_output("")

        elif cmd_lower == "date":
            from datetime import datetime
            self.add_output(datetime.now().strftime("%a %b %d %H:%M:%S %Z %Y"))
            self.add_output("")

        elif cmd_lower == "uptime":
            ticks = pygame.time.get_ticks()
            secs = ticks // 1000
            hours = secs // 3600
            mins = (secs % 3600) // 60
            self.add_output(f" up {hours}:{mins:02d}, 1 user, load average: 0.42, 0.38, 0.35")
            self.add_output("")

        elif cmd_lower == "id":
            user = self.filesystem.get_current_user()
            if user == "root":
                self.add_output("uid=0(root) gid=0(root) groups=0(root)")
            else:
                self.add_output("uid=1000(pilot) gid=1000(users) groups=1000(users)")
            self.add_output("")

        elif cmd_lower in ["env", "printenv"]:
            user = self.filesystem.get_current_user()
            env_vars = [
                f"USER={user}",
                f"HOME=/home/pilot/blthll",
                "SHELL=/bin/bash",
                "PATH=/usr/local/bin:/usr/bin:/bin",
                "TERM=xterm-256color",
                "LANG=en_US.UTF-8",
                "HOSTNAME=blthll-terminal",
                f"PWD={self.filesystem.get_pwd()}",
                "EDITOR=vim",
                "BLTHLL_VERSION=1.0.0",
            ]
            for var in env_vars:
                self.add_output(var)
            self.add_output("")

        elif cmd_lower in ["stat", "cat", "touch", "mkdir", "rm", "rmdir", "mv", "chmod",
                           "vim", "vi", "edit", "emacs", "python", "run", "kill", "man",
                           "cd", "head", "tail", "grep", "wc", "file", "cp"]:
            # Commands that require arguments - show usage
            usage_map = {
                'stat': ("stat: missing file operand", "Usage: stat <filename>"),
                'cat': ("cat: missing file operand", "Usage: cat <filename>"),
                'touch': ("touch: missing file operand", "Usage: touch <filename>"),
                'mkdir': ("mkdir: missing directory operand", "Usage: mkdir <directory>"),
                'rmdir': ("rmdir: missing directory operand", "Usage: rmdir <directory>"),
                'rm': ("rm: missing operand", "Usage: rm <filename>"),
                'mv': ("mv: missing file operand", "Usage: mv <source> <destination>"),
                'chmod': ("chmod: missing operand", "Usage: chmod <mode> <filename>"),
                'vim': ("vim: missing file operand", "Usage: vim <filename>"),
                'vi': ("vi: missing file operand", "Usage: vi <filename>"),
                'edit': ("edit: missing file operand", "Usage: edit <filename>"),
                'emacs': ("emacs: missing file operand", "Usage: emacs <filename>"),
                'python': ("python: missing file operand", "Usage: python <script.py>"),
                'run': ("run: missing file operand", "Usage: run <script.py>"),
                'kill': ("kill: missing operand", "Usage: kill [-signal] <pid>"),
                'man': ("man: missing topic operand", "Usage: man <topic>"),
                'head': ("head: missing file operand", "Usage: head [-n N] <file>"),
                'tail': ("tail: missing file operand", "Usage: tail [-n N] <file>"),
                'grep': ("grep: missing pattern", "Usage: grep [-i] [-n] <pattern> <file>"),
                'wc': ("wc: missing file operand", "Usage: wc <file>"),
                'file': ("file: missing file operand", "Usage: file <name>"),
                'cp': ("cp: missing file operand", "Usage: cp <source> <destination>"),
                'cd': (None, None),  # Special handling below
            }
            if cmd_lower == "cd":
                # cd without args goes to home (standard Unix behavior)
                self.filesystem.current_path = ['home', 'pilot', 'blthll']
            else:
                msg, usage = usage_map.get(cmd_lower, (f"{cmd_lower}: missing operand", ""))
                self.add_output(msg)
                self.add_output(usage)
            self.add_output("")
        
        elif self._easter_egg_commands(cmd_lower=cmd_lower, command=command):
            return
        
        else:
            self.add_output(f"Command not found: {command}")
            self.add_output("Type 'help' for available commands")
            self.add_output("")
    
    # Commands that take directory arguments (use directory completions)
    _DIR_COMPLETION_CMDS = {'cd', 'ls', 'find'}
    # Commands that take file arguments (use file completions)
    _FILE_COMPLETION_CMDS = {
        'cat', 'vim', 'vi', 'edit', 'emacs', 'python', 'run', 'rm',
        'chmod', 'stat', 'mv', 'cp', 'head', 'tail', 'wc', 'file',
        'readme', 'grep',
    }

    def _handle_tab_completion(self):
        """Handle tab completion for commands that take file/directory arguments"""
        if not self.input_buffer:
            return

        parts = self.input_buffer.split()
        if len(parts) == 0:
            return

        command = parts[0].lower()

        # Check if this command supports completion
        if command not in self._DIR_COMPLETION_CMDS and command not in self._FILE_COMPLETION_CMDS:
            return

        # Get the partial path/filename being typed
        # For grep, the file arg is the 3rd token (grep pattern file)
        if command == 'grep':
            if len(parts) < 3:
                return  # Need at least grep + pattern before completing file
            partial = parts[-1] if len(parts) >= 3 else ""
        elif command == 'chmod':
            if len(parts) < 3:
                # Still typing mode, no file completion yet
                if len(parts) == 2:
                    return
                partial = ""
            else:
                partial = parts[2]
        elif command in ('mv', 'cp'):
            # Complete the current (last) argument
            if len(parts) == 1:
                partial = ""
            else:
                partial = parts[-1]
        else:
            if len(parts) == 1:
                partial = ""
            else:
                partial = parts[1]

        # Get appropriate completions
        if command in self._DIR_COMPLETION_CMDS:
            completions = self._get_directory_completions(partial)
        else:
            completions = self._get_file_completions(partial)
        
        if not completions:
            return
        
        # If only one completion, auto-complete it
        if len(completions) == 1:
            completion = completions[0]
            # For cd command, add trailing slash to directories to enable further path completion
            # But only if the completion doesn't already have a path with slash
            if command == 'cd' and not completion.endswith('/') and not completion == '..' and '/' not in completion:
                # It's a simple directory name - add slash to enable path continuation
                completion = completion + '/'
            elif command == 'cd' and '/' in completion and not completion.endswith('/') and not completion.endswith('/..'):
                # It's a path completion - add trailing slash
                completion = completion + '/'
            
            # Rebuild the command with the completion replacing the appropriate token
            # For multi-arg commands, replace the last token
            prefix_parts = parts[:-1] if len(parts) > 1 else [command]
            self.input_buffer = ' '.join(prefix_parts) + ' ' + completion
        else:
            # Multiple completions - show them with wrapping
            self.add_output("")
            self._format_ls_output(completions, separator="  ")
            self.add_output("")
    
    def _format_ls_output(self, items, separator="  "):
        """
        Format ls output with wrapping based on terminal width
        
        Args:
            items: List of file/directory names
            separator: String to separate items (default: "  ")
        """
        if not items:
            return
        
        # Get available width (leave 2 char margin on each side)
        available_width = self.renderer.char_width - 2
        
        # Build lines
        current_line = ""
        for item in items:
            # Calculate what the line would look like with this item
            if current_line:
                test_line = current_line + separator + item
            else:
                test_line = item
            
            # Check if it fits
            if len(test_line) <= available_width:
                # Fits - add to current line
                if current_line:
                    current_line += separator + item
                else:
                    current_line = item
            else:
                # Doesn't fit - output current line and start new one
                if current_line:
                    self.add_output(current_line)
                # Start new line with this item (even if it's too long, we'll add it)
                current_line = item
        
        # Output remaining line
        if current_line:
            self.add_output(current_line)
    
    def _get_directory_completions(self, partial):
        """Get directory name completions, supporting path completion"""
        # Handle path completion (e.g., "home/pilot/" or "home/pilot/b")
        if '/' in partial:
            # Check if it ends with a slash
            ends_with_slash = partial.endswith('/')
            # Split into path and filename parts
            path_parts = partial.rsplit('/', 1)
            if len(path_parts) == 2 and path_parts[1]:
                # Has both path and partial filename (e.g., "home/pilot/b")
                parent_path = path_parts[0]
                filename_partial = path_parts[1]
            elif ends_with_slash:
                # Ends with /, so everything before is the path (e.g., "home/pilot/")
                parent_path = partial.rstrip('/')
                filename_partial = ""
            else:
                # Has / but no trailing slash and no filename part (shouldn't happen, but handle it)
                parent_path = partial
                filename_partial = ""
            
            # Save current directory
            original_path = self.filesystem.current_path[:]
            
            # Try to navigate to parent directory
            if parent_path:
                # Handle absolute paths
                if parent_path.startswith('/'):
                    target_path = [p for p in parent_path.split('/') if p]
                elif parent_path == '~':
                    target_path = ['home', 'pilot', 'blthll']
                else:
                    # Relative path - build from current path
                    path_components = [p for p in parent_path.split('/') if p]
                    target_path = self.filesystem.current_path + path_components
                
                # Check if path exists and navigate there
                if self.filesystem._directory_exists(target_path):
                    self.filesystem.current_path = target_path
                else:
                    # Path doesn't exist, restore and return empty
                    self.filesystem.current_path = original_path
                    return []
            else:
                # Empty parent path - stay in current directory
                filename_partial = partial.lstrip('/')
            
            # Get completions from the target directory
            show_hidden = filename_partial.startswith('.') if filename_partial else False
            all_contents = self.filesystem.list_directory(show_hidden=show_hidden)
            
            # Filter for directories
            matches = []
            for item in all_contents:
                if item.endswith('/'):
                    dir_name = item[:-1]  # Remove trailing slash
                    if not filename_partial or dir_name.startswith(filename_partial):
                        # Return full path relative to original directory
                        if parent_path:
                            matches.append(f"{parent_path}/{dir_name}")
                        else:
                            matches.append(dir_name)
            
            # Restore original directory
            self.filesystem.current_path = original_path
            
            # Also include .. if it starts with partial and we're in a subdirectory
            if (not filename_partial or "..".startswith(filename_partial)) and len(target_path) > 1:
                if parent_path:
                    # Calculate parent of parent_path
                    if '/' in parent_path:
                        parent_parts = parent_path.split('/')
                        if len(parent_parts) > 1:
                            parent_of_parent = '/'.join(parent_parts[:-1])
                            matches.append(f"{parent_of_parent}/.." if parent_of_parent else "..")
                        else:
                            matches.append("..")
                    else:
                        matches.append("..")
                else:
                    matches.append("..")
            
            return sorted(matches)
        
        # No path - just complete from current directory
        show_hidden = partial.startswith('.')
        all_contents = self.filesystem.list_directory(show_hidden=show_hidden)
        
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
        # Show hidden files if user starts typing with a dot
        show_hidden = partial.startswith('.')
        # Get all contents (includes user-created)
        all_contents = self.filesystem.list_directory(show_hidden=show_hidden)
        
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
    
    def _check_puzzle_triggers(self, trigger):
        """Run puzzle checks for the given trigger ('rm', 'chmod'). Return list of (game, message) for newly unlocked."""
        return check_puzzles(self.filesystem, self.game.save_system, trigger)

    def _get_man_pages(self):
        """Return dictionary of short man page entries for common commands."""
        return {
            'ls': [
                "LS(1)                    BLTHLL Terminal Manual                    LS(1)",
                "",
                "NAME",
                "       ls - list directory contents",
                "",
                "SYNOPSIS",
                "       ls [-la] [path]",
                "",
                "DESCRIPTION",
                "       List information about files in the current directory or at path.",
                "",
                "OPTIONS",
                "       -l     Long format: show permissions, owner, and name",
                "       -a     Show hidden files (names starting with .)",
                "",
                "EXAMPLES",
                "       ls                List files in current directory",
                "       ls -la            Long listing with hidden files",
                "       ls /var/log       List files in /var/log",
            ],
            'cd': [
                "CD(1)                    BLTHLL Terminal Manual                    CD(1)",
                "",
                "NAME",
                "       cd - change the working directory",
                "",
                "SYNOPSIS",
                "       cd [path]",
                "",
                "DESCRIPTION",
                "       Change the current directory to path. With no arguments, changes",
                "       to the home directory. Supports '..' for parent, '~' for home,",
                "       and absolute paths starting with '/'.",
                "",
                "       TAB completion is available for directory names.",
            ],
            'cat': [
                "CAT(1)                   BLTHLL Terminal Manual                   CAT(1)",
                "",
                "NAME",
                "       cat - concatenate and print files",
                "",
                "SYNOPSIS",
                "       cat <file>",
                "",
                "DESCRIPTION",
                "       Read the contents of file and print to standard output.",
                "       Supports relative paths (e.g., cat data/secret/file.txt).",
            ],
            'chmod': [
                "CHMOD(1)                 BLTHLL Terminal Manual                 CHMOD(1)",
                "",
                "NAME",
                "       chmod - change file mode bits",
                "",
                "SYNOPSIS",
                "       chmod <mode> <file>",
                "",
                "DESCRIPTION",
                "       Change the permissions of a file.",
                "",
                "       Modes can be specified as:",
                "         Octal:    chmod 755 file.py   (rwxr-xr-x)",
                "         Octal:    chmod 644 data.txt  (rw-r--r--)",
                "         Symbolic: chmod rwxr-xr-x file.py",
                "",
                "       Only the file owner (or root) can change permissions.",
            ],
            'rm': [
                "RM(1)                    BLTHLL Terminal Manual                    RM(1)",
                "",
                "NAME",
                "       rm - remove files or directories",
                "",
                "SYNOPSIS",
                "       rm <file>",
                "       rm -r <directory>",
                "",
                "DESCRIPTION",
                "       Remove files. With -r, remove directories recursively.",
                "       Recursive delete only works on user-created directories.",
            ],
            'mv': [
                "MV(1)                    BLTHLL Terminal Manual                    MV(1)",
                "",
                "NAME",
                "       mv - move or rename files",
                "",
                "SYNOPSIS",
                "       mv <source> <destination>",
                "",
                "DESCRIPTION",
                "       Move source to destination, or rename if in the same directory.",
                "       Preserves permissions and ownership.",
            ],
            'cp': [
                "CP(1)                    BLTHLL Terminal Manual                    CP(1)",
                "",
                "NAME",
                "       cp - copy files",
                "",
                "SYNOPSIS",
                "       cp <source> <destination>",
                "",
                "DESCRIPTION",
                "       Copy source file to destination. Preserves permissions.",
            ],
            'kill': [
                "KILL(1)                  BLTHLL Terminal Manual                  KILL(1)",
                "",
                "NAME",
                "       kill - send a signal to a process",
                "",
                "SYNOPSIS",
                "       kill [-signal] <pid>",
                "",
                "DESCRIPTION",
                "       Send a signal to a process. Default signal terminates the process.",
                "       Use 'ps' or 'top' to find process IDs.",
                "",
                "EXAMPLES",
                "       kill 1234          Terminate process 1234",
                "       kill -9 1234       Force kill process 1234",
            ],
            'top': [
                "TOP(1)                   BLTHLL Terminal Manual                   TOP(1)",
                "",
                "NAME",
                "       top - display system processes",
                "",
                "SYNOPSIS",
                "       top",
                "",
                "DESCRIPTION",
                "       Interactive process viewer. Shows CPU usage, memory, and more.",
                "       Press 'q' to quit, 'k' to kill a process.",
            ],
            'ps': [
                "PS(1)                    BLTHLL Terminal Manual                    PS(1)",
                "",
                "NAME",
                "       ps - report a snapshot of current processes",
                "",
                "SYNOPSIS",
                "       ps [aux]",
                "",
                "DESCRIPTION",
                "       Display currently running processes with PID, command, CPU and",
                "       memory usage. Flags like 'aux' and '-ef' are accepted.",
            ],
            'grep': [
                "GREP(1)                  BLTHLL Terminal Manual                  GREP(1)",
                "",
                "NAME",
                "       grep - search file contents for a pattern",
                "",
                "SYNOPSIS",
                "       grep [-i] [-n] <pattern> <file>",
                "",
                "DESCRIPTION",
                "       Search for lines matching pattern in file.",
                "",
                "OPTIONS",
                "       -i     Case-insensitive search",
                "       -n     Prefix each matching line with its line number",
                "",
                "EXAMPLES",
                "       grep error /var/log/boot.log",
                "       grep -in failed boot.log",
            ],
            'find': [
                "FIND(1)                  BLTHLL Terminal Manual                  FIND(1)",
                "",
                "NAME",
                "       find - search for files in a directory hierarchy",
                "",
                "SYNOPSIS",
                "       find [path] [-name pattern]",
                "",
                "DESCRIPTION",
                "       Recursively list files and directories. Optionally filter by name",
                "       using shell glob patterns.",
                "",
                "EXAMPLES",
                "       find                List everything under current directory",
                "       find . -name '*.py' Find all Python files",
                "       find /var -name log Find items named 'log' under /var",
            ],
            'systemctl': [
                "SYSTEMCTL(1)             BLTHLL Terminal Manual             SYSTEMCTL(1)",
                "",
                "NAME",
                "       systemctl - control the systemd system and service manager",
                "",
                "SYNOPSIS",
                "       systemctl <command> [service]",
                "",
                "COMMANDS",
                "       status <service>     Show service status",
                "       start <service>      Start a service",
                "       stop <service>       Stop a service",
                "       enable <service>     Enable at boot (requires sudo)",
                "       disable <service>    Disable at boot (requires sudo)",
                "       list-units           List all active units",
                "       list-unit-files      List installed unit files",
                "",
                "DESCRIPTION",
                "       Services are defined in /usr/lib/systemd/system/.",
                "       Drop-in overrides can be placed in /etc/systemd/system/<service>.d/.",
                "       Services have dependencies (Requires=) and conflicts (Conflicts=).",
            ],
            'head': [
                "HEAD(1)                  BLTHLL Terminal Manual                  HEAD(1)",
                "",
                "NAME",
                "       head - output the first part of files",
                "",
                "SYNOPSIS",
                "       head [-n N] <file>",
                "",
                "DESCRIPTION",
                "       Print the first 10 lines of file. Use -n to specify a number.",
            ],
            'tail': [
                "TAIL(1)                  BLTHLL Terminal Manual                  TAIL(1)",
                "",
                "NAME",
                "       tail - output the last part of files",
                "",
                "SYNOPSIS",
                "       tail [-n N] <file>",
                "",
                "DESCRIPTION",
                "       Print the last 10 lines of file. Use -n to specify a number.",
            ],
            'sudo': [
                "SUDO(8)                  BLTHLL Terminal Manual                  SUDO(8)",
                "",
                "NAME",
                "       sudo - execute a command as root",
                "",
                "SYNOPSIS",
                "       sudo <command>",
                "       sudo !!           Re-run last command as root",
                "",
                "DESCRIPTION",
                "       Execute a command with superuser privileges. You will be prompted",
                "       for the password. Authentication is cached for 5 minutes.",
            ],
        }

    def _handle_sudo_command(self, command):
        """
        Handle sudo command execution
        
        Args:
            command: The command to execute with sudo
        """
        if not command:
            self.add_output("usage: sudo <command>")
            self.add_output("")
            return

        # Handle sudo !! (re-run last command as root)
        if command == "!!":
            # Find the last non-sudo command in history
            if len(self.command_history) >= 2:
                command = self.command_history[-2]  # -1 is "sudo !!" itself
                self.add_output(f"sudo {command}")
            else:
                self.add_output("bash: !!: event not found")
                self.add_output("")
                return

        # Check if sudo is already valid
        if self._is_sudo_valid():
            # Execute command as root
            self._execute_as_root(command)
        else:
            # Need password - prompt for it
            self.pending_sudo_command = command
            self.waiting_for_password = True
            # Don't add output here - get_prompt() will show password prompt
    
    def _check_sudo_password(self, password):
        """
        Check if the provided sudo password is correct
        
        Args:
            password: The password entered by user
        """
        if password == self.sudo_password:
            # Correct password
            self.sudo_authenticated = True
            self.sudo_timestamp = pygame.time.get_ticks()
            self.add_output("")
            
            # Execute the pending command
            if self.pending_sudo_command:
                self._execute_as_root(self.pending_sudo_command)
                self.pending_sudo_command = None
            
            self._mark_secret_found("sudo_user")
        else:
            # Wrong password
            self.add_output("")
            self.add_output("Sorry, try again.")
            self.add_output("")
            self.pending_sudo_command = None
    
    def _is_sudo_valid(self):
        """Check if sudo authentication is still valid"""
        if not self.sudo_authenticated:
            return False
        
        # Check if timeout has expired
        current_time = pygame.time.get_ticks()
        if current_time - self.sudo_timestamp > self.sudo_timeout:
            self.sudo_authenticated = False
            return False
        
        return True
    
    def _execute_as_root(self, command):
        """
        Execute a command with root privileges
        
        Args:
            command: The command to execute
        """
        # Temporarily become root
        original_user = self.filesystem.get_current_user()
        self.filesystem.set_user("root")
        
        try:
            # Execute the command
            self.execute_command(command)
        finally:
            # Always restore original user
            self.filesystem.set_user(original_user)
    
    def _show_processes(self):
        """Display static process list (ps command)"""
        # Update CPU usage for some variation
        self.process_manager.update_cpu_usage()
        
        processes = self.process_manager.get_processes()
        
        # Column headers
        header = f"{'PID':<8} {'COMMAND':<20} {'%CPU':<8} {'MEM':<10} {'USER':<8} {'TIME':<10}"
        self.add_output(header)
        
        # Show all processes
        for proc in processes:
            line = f"{proc.pid:<8} {proc.command:<20} {proc.cpu:<7.1f} {proc.mem:.1f}M{'':<5} {proc.user:<8} {proc.time_str:<10}"
            self.add_output(line)
        
        self.add_output("")
        self.add_output(f"Tip: Use 'top' for interactive view or 'kill <pid>' to terminate")
        self.add_output("")
        
        self._mark_secret_found("process_viewer")
    
    def _kill_process(self, pid):
        """
        Kill a process by PID
        
        Args:
            pid: Process ID to kill
        """
        success, message, was_virus = self.process_manager.remove_process(pid)
        
        if success:
            self.add_output(message)
            
            if was_virus:
                # Player killed the virus!
                self.add_output("")
                self.add_output("=" * 50)
                self.add_output("ALERT: Malicious process terminated!")
                self.add_output("=" * 50)
                self.add_output("")
                self.add_output("System scan complete...")
                self.add_output("Threat neutralized.")
                self.add_output("Performance restored to optimal levels.")
                self.add_output("")
                self.add_output("You have uncovered a hidden threat!")
                self.add_output("")
                self.add_output("New system utility unlocked: 'start spacebullets'")
                self.add_output("")
                self._mark_secret_found("virus_hunter")
                
                # Unlock the galaga game
                self.game.save_system.mark_virus_killed()
                self.process_manager.mark_virus_discovered()
            else:
                # Killed a normal process - might have side effects
                proc = None
                # We can't get the proc anymore since it's deleted, but we have the message
                if "python" in message.lower():
                    self.add_output("Note: Python interpreter terminated")
                elif "vim" in message.lower() or "emacs" in message.lower():
                    self.add_output("Note: Text editor terminated")
        else:
            self.add_output(message)
        
        self.add_output("")
    
    def _systemctl_status(self, service_name):
        """Show status of a systemd service"""
        state = self.systemd_manager.get_service_state(service_name)
        enabled = self.systemd_manager.is_enabled(service_name)
        
        # Normalize service name
        if not service_name.endswith('.service'):
            service_name = service_name + '.service'
        
        # Check if unit file exists
        if not self.systemd_manager._unit_file_exists(service_name):
            self.add_output(f"● {service_name} - not found")
            self.add_output("")
            return
        
        # Get unit file path (for puzzle clue)
        unit_path = self.systemd_manager._resolve_unit_path(service_name)
        
        # Format status output similar to real systemctl
        status_symbol = "●" if state == 'active' else "○"
        state_display = state.capitalize()
        enabled_display = "enabled" if enabled else "disabled"
        
        self.add_output(f"{status_symbol} {service_name} - {state_display} ({enabled_display})")
        if unit_path:
            self.add_output(f"   Loaded: {unit_path}")
        self.add_output("")
    
    def _systemctl_start(self, service_name):
        """Start a systemd service"""
        # Clear any previous reset flag
        self.systemd_manager.clear_reset_flag()
        
        success, message = self.systemd_manager.start_service(service_name)
        self.add_output(message)
        self.add_output("")
        
        # Check if system reset was triggered
        if self.systemd_manager.was_system_reset_triggered():
            self.add_output("=" * 60)
            self.add_output("SYSTEM RESET DETECTED")
            self.add_output("=" * 60)
            self.add_output("")
            self.systemd_manager.clear_reset_flag()
        
        # Check puzzle triggers after systemctl start (for dependency puzzle)
        # Save filesystem state first in case files were created
        self._save_filesystem()
        for _game, msg in self._check_puzzle_triggers("systemctl"):
            self.add_output("")
            self.add_output(msg)
    
    def _systemctl_stop(self, service_name):
        """Stop a systemd service"""
        # Clear any previous reset flag
        self.systemd_manager.clear_reset_flag()
        
        success, message = self.systemd_manager.stop_service(service_name)
        self.add_output(message)
        self.add_output("")
        
        # Check if system reset was triggered
        if self.systemd_manager.was_system_reset_triggered():
            self.add_output("=" * 60)
            self.add_output("SYSTEM RESET DETECTED")
            self.add_output("=" * 60)
            self.add_output("")
            self.systemd_manager.clear_reset_flag()
    
    def _systemctl_enable(self, service_name):
        """Enable a systemd service"""
        # Require root privileges
        if self.filesystem.get_current_user() != "root":
            self.add_output(f"systemctl: Operation failed: Access denied")
            self.add_output("Note: Enabling services requires root privileges. Use 'sudo systemctl enable <service>'")
            self.add_output("")
            return
        
        success, message = self.systemd_manager.enable_service(service_name)
        self.add_output(message)
        self.add_output("")
        
        # Check puzzle triggers after systemctl enable
        if success:
            self._save_filesystem()
            for _game, msg in self._check_puzzle_triggers("systemctl"):
                self.add_output("")
                self.add_output(msg)
    
    def _systemctl_disable(self, service_name):
        """Disable a systemd service"""
        # Require root privileges
        if self.filesystem.get_current_user() != "root":
            self.add_output(f"systemctl: Operation failed: Access denied")
            self.add_output("Note: Disabling services requires root privileges. Use 'sudo systemctl disable <service>'")
            self.add_output("")
            return
        
        success, message = self.systemd_manager.disable_service(service_name)
        self.add_output(message)
        self.add_output("")
    
    def _systemctl_list_units(self):
        """List all systemd units"""
        units = self.systemd_manager.list_units()
        
        if not units:
            self.add_output("No units found.")
            self.add_output("")
            return
        
        # Header
        self.add_output(f"{'UNIT':<30} {'LOAD':<8} {'ACTIVE':<12} {'SUB':<12} {'ENABLED':<10}")
        self.add_output("-" * 80)
        
        # List units
        for service_name, state, enabled in units:
            load = "loaded"
            active = state
            sub = "running" if state == 'active' else "dead"
            enabled_str = "enabled" if enabled else "disabled"
            
            self.add_output(f"{service_name:<30} {load:<8} {active:<12} {sub:<12} {enabled_str:<10}")
        
        self.add_output("")
        self.add_output(f"{len(units)} unit(s) listed.")
        self.add_output("")
    
    def _systemctl_list_unit_files(self):
        """List all systemd unit files"""
        unit_files = self.systemd_manager.list_unit_files()
        
        if not unit_files:
            self.add_output("No unit files found.")
            self.add_output("")
            return
        
        # Header
        self.add_output(f"{'UNIT FILE':<40} {'STATE':<12} {'LOCATION':<30}")
        self.add_output("-" * 90)
        
        # List unit files
        for service_name, location, enabled in unit_files:
            state = "enabled" if enabled else "disabled"
            self.add_output(f"{service_name:<40} {state:<12} {location:<30}")
        
        self.add_output("")
        self.add_output(f"{len(unit_files)} unit file(s) listed.")
        self.add_output("")
    
    def _is_systemctl_available(self):
        """
        Check if systemctl is "installed" (Stage 1 puzzle check).
        Systemctl is available if /bin/systemctl exists and is executable.
        
        Returns:
            bool: True if systemctl is available, False otherwise
        """
        old_pwd = self.filesystem.get_pwd()
        self.filesystem.change_directory('/bin')
        available = self.filesystem.file_exists('systemctl')
        if available:
            # Check if it's executable
            perms = self.filesystem.get_permissions('systemctl')
            if perms and 'x' in perms[:3]:  # Check user execute permission
                self.filesystem.change_directory(old_pwd)
                return True
        self.filesystem.change_directory(old_pwd)
        return False
    
    def get_prompt(self):
        """Get the current prompt string with directory"""
        # If showing save prompt, show empty prompt (prompt is in output)
        if self.showing_save_prompt:
            return ""
        # If waiting for password, show password prompt
        if self.waiting_for_password:
            return "[sudo] password: "
        
        # Get just the last part of the path for brevity
        path_parts = self.filesystem.current_path
        if path_parts:
            current_dir = path_parts[-1]
        else:
            current_dir = "/"
        return f"[{current_dir}]> "
    
    def add_output(self, text):
        """Add a line to the output buffer instantly"""
        self.output_lines.append(text)
        
        # Trim old lines if too many
        if len(self.output_lines) > 1000:
            self.output_lines = self.output_lines[-1000:]
        
        # When new output is added, auto-scroll to bottom if already at bottom
        # This keeps new output visible while allowing manual scrolling
        if self.scroll_offset == 0:
            # Already at bottom, stay at bottom to show new output
            pass
        # Otherwise, keep current scroll position (user is reading older output)
    
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
        
        # Calculate start index based on scroll offset
        # scroll_offset = 0 means show most recent (bottom)
        # Higher scroll_offset means scroll back further (toward top)
        max_scroll = max(0, len(self.output_lines) - visible_lines)
        self.scroll_offset = min(self.scroll_offset, max_scroll)  # Clamp scroll offset
        
        if len(self.output_lines) <= visible_lines:
            # All lines fit, show all
            start_idx = 0
        else:
            # Calculate start index: from bottom, scroll_offset lines back
            start_idx = max(0, len(self.output_lines) - visible_lines - self.scroll_offset)
        
        visible_output = self.output_lines[start_idx:start_idx + visible_lines]
        
        # Draw output lines
        for i, line in enumerate(visible_output):
            self.renderer.write(1, i + 1, line[:self.renderer.char_width - 2])
        
        # Draw input line at bottom
        input_y = self.renderer.char_height - 1
        
        # Draw border line
        self.renderer.write(0, input_y - 1, "-" * self.renderer.char_width, 
                          self.renderer.COLORS['menu_normal'])
        
        # Show scroll indicator if scrolled
        if self.scroll_offset > 0:
            visible_lines = self.renderer.char_height - 2
            max_scroll = max(0, len(self.output_lines) - visible_lines)
            if max_scroll > 0:
                scroll_pct = int((self.scroll_offset / max_scroll) * 100) if max_scroll > 0 else 0
                scroll_indicator = f" [Scroll: {scroll_pct}%]"
                scroll_x = self.renderer.char_width - len(scroll_indicator) - 1
                if scroll_x > 0:
                    self.renderer.write(scroll_x, input_y - 1, scroll_indicator, 
                                      self.renderer.COLORS['menu_normal'])
        
        # Draw prompt and input
        prompt = self.get_prompt()
        input_text = prompt + self.input_buffer
        self.renderer.write(0, input_y, input_text, self.renderer.COLORS['menu_selected'])
        
        # Draw cursor
        if self.cursor_visible and (not self.booting or self.showing_save_prompt):
            cursor_x = len(input_text)
            if cursor_x < self.renderer.char_width:
                self.renderer.write(cursor_x, input_y, "█", self.renderer.COLORS['menu_selected'])
        
        # If booting, show "Press any key" hint
        if self.booting and self.boot_index >= len(self.boot_sequence):
            hint_y = self.renderer.char_height - 3
            hint = "[Press any key to continue]"
            self.renderer.write_centered(hint_y, hint, self.renderer.COLORS['menu_normal'])
        
        # If showing intro and waiting for key, show hint
        if self.showing_intro and self.intro_waiting_for_key and not self.is_typing:
            hint_y = self.renderer.char_height - 3
            hint = "[Press any key to continue]"
            self.renderer.write_centered(hint_y, hint, self.renderer.COLORS['menu_normal'])
        
        self.renderer.render()
