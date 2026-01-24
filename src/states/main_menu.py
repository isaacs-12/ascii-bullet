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
            self.add_output("Loading saved game...")
            self.add_output("(Save system not implemented yet)")
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
        
        elif cmd_lower.startswith("ls -"):
            # List files with details (including permissions)
            args = cmd_lower[4:].strip()
            show_hidden = "a" in args  # Show hidden files if -a flag is present
            if args in ["l", "la", "al", "a", ""]:
                items = self.filesystem.list_directory(show_hidden=show_hidden)
                if items:
                    # Show detailed listing with permissions and owner
                    for item in items:
                        if item.endswith('/'):
                            # Directory - get owner (will default to current user if not specified)
                            owner = self.filesystem.get_file_owner(item)
                            self.add_output(f"drwxr-xr-x  {owner:6}  {item}")
                        else:
                            # File - show actual permissions and owner
                            perms = self.filesystem.get_permissions(item)
                            owner = self.filesystem.get_file_owner(item)
                            if perms:
                                # If permissions are 3 characters, pad to 9 for display
                                if len(perms) == 3:
                                    perms_display = perms + "------"
                                elif len(perms) == 9:
                                    perms_display = perms
                                else:
                                    perms_display = perms + "-" * (9 - len(perms))
                                self.add_output(f"-{perms_display}  {owner:6}  {item}")
                            else:
                                self.add_output(f"-rw-------  {owner:6}  {item}")
                else:
                    self.add_output("(empty directory)")
            else:
                self.add_output(f"ls: invalid option -- '{args}'")
            self.add_output("")
            # Track directory visit
            current_path = self.filesystem.get_pwd()
            self.game.save_system.mark_directory_visited(current_path)
        
        elif cmd_lower in ["ls", "dir"]:
            # List directory contents (hidden files not shown by default)
            contents = self.filesystem.list_directory(show_hidden=False)
            if contents:
                # Format with wrapping based on terminal width
                self._format_ls_output(contents)
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
            else:
                self.add_output(f"No manual entry for '{topic}'")
                self.add_output("Available manual pages: python")
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
            self.add_output(f"Device: 0h/{0:<10} Inode: 0     Links: 1")
            self.add_output(f"Access: ({perms_display})  Uid: ({owner})   Gid: (users)")
            self.add_output(f"Access: {access_str}")
            self.add_output(f"Modify: {modify_str}")
            self.add_output(f"Change: {change_str}")
            self.add_output("")
        
        elif cmd_lower.startswith("touch "):
            # Create empty file
            filename = command[6:].strip()
            success, error = self.filesystem.create_file(filename)
            if success:
                self.add_output(f"Created file: {filename}")
                self._save_filesystem()
                # Check puzzle triggers after file creation (might create override files)
                if '/etc/systemd/system/' in filename and '.d/' in filename:
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
                if '/etc/systemd/system/' in dirname and '.d' in dirname:
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
                    if '/etc/systemd/system/' in filename and '.d/' in filename:
                        for _game, msg in self._check_puzzle_triggers("systemctl"):
                            self.add_output("")
                            self.add_output(msg)
                else:
                    self.add_output(error)
                self.add_output("")
            else:
                self.add_output("Invalid syntax. Use: echo text > file  or  echo text >> file")
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
        
        elif cmd_lower == "ps":
            # Static process list
            self._show_processes()
        
        elif cmd_lower.startswith("kill "):
            # Kill a process
            try:
                pid_str = command[5:].strip()
                pid = int(pid_str)
                self._kill_process(pid)
            except ValueError:
                self.add_output(f"kill: invalid process id: {command[5:].strip()}")
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
        
        elif cmd_lower in ["stat", "cat", "touch", "mkdir", "rm", "rmdir", "mv", "chmod", "vim", "vi", "edit", "emacs", "python", "run", "kill", "man", "cd"]:
            # Commands that require arguments - show usage
            # Note: systemctl is handled separately above
            if cmd_lower == "stat":
                self.add_output("stat: missing file operand")
                self.add_output("Usage: stat <filename>")
            elif cmd_lower == "cat":
                self.add_output("cat: missing file operand")
                self.add_output("Usage: cat <filename>")
            elif cmd_lower == "touch":
                self.add_output("touch: missing file operand")
                self.add_output("Usage: touch <filename>")
            elif cmd_lower == "mkdir":
                self.add_output("mkdir: missing directory operand")
                self.add_output("Usage: mkdir <directory>")
            elif cmd_lower == "rmdir":
                self.add_output("rmdir: missing directory operand")
                self.add_output("Usage: rmdir <directory>")
            elif cmd_lower == "rm":
                self.add_output("rm: missing operand")
                self.add_output("Usage: rm <filename>")
            elif cmd_lower == "mv":
                self.add_output("mv: missing file operand")
                self.add_output("Usage: mv <source> <destination>")
            elif cmd_lower == "chmod":
                self.add_output("chmod: missing operand")
                self.add_output("Usage: chmod <mode> <filename>")
            elif cmd_lower in ["vim", "vi", "edit"]:
                self.add_output(f"{cmd_lower}: missing file operand")
                self.add_output(f"Usage: {cmd_lower} <filename>")
            elif cmd_lower == "emacs":
                self.add_output("emacs: missing file operand")
                self.add_output("Usage: emacs <filename>")
            elif cmd_lower in ["python", "run"]:
                self.add_output(f"{cmd_lower}: missing file operand")
                self.add_output(f"Usage: {cmd_lower} <script.py>")
            elif cmd_lower == "kill":
                self.add_output("kill: missing operand")
                self.add_output("Usage: kill <pid>")
            elif cmd_lower == "man":
                self.add_output("man: missing topic operand")
                self.add_output("Usage: man <topic>")
            elif cmd_lower == "cd":
                # cd without args goes to home (standard Unix behavior)
                home_path = "home/pilot/blthll"
                old_path = self.filesystem.current_path[:]
                success, error = self.filesystem.change_directory(home_path)
                if success:
                    self.add_output("")
                else:
                    self.add_output(f"cd: {error}")
                    self.add_output("")
            self.add_output("")
        
        elif self._easter_egg_commands(cmd_lower=cmd_lower, command=command):
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
            completion = completions[0]
            # For cd command, add trailing slash to directories to enable further path completion
            # But only if the completion doesn't already have a path with slash
            if command == 'cd' and not completion.endswith('/') and not completion == '..' and '/' not in completion:
                # It's a simple directory name - add slash to enable path continuation
                completion = completion + '/'
            elif command == 'cd' and '/' in completion and not completion.endswith('/') and not completion.endswith('/..'):
                # It's a path completion - add trailing slash
                completion = completion + '/'
            
            if len(parts) == 1:
                self.input_buffer = f"{command} {completion}"
            else:
                # For path completions, the completion already includes the full path
                # For simple completions, just replace the partial
                if '/' in partial:
                    # Path completion - use the full completion as-is (it already has the path)
                    self.input_buffer = f"{command} {completion}"
                else:
                    # Simple completion - just replace
                    self.input_buffer = f"{command} {completion}"
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
        success, message = self.systemd_manager.start_service(service_name)
        self.add_output(message)
        self.add_output("")
        
        # Check puzzle triggers after systemctl start (for dependency puzzle)
        # Save filesystem state first in case files were created
        self._save_filesystem()
        for _game, msg in self._check_puzzle_triggers("systemctl"):
            self.add_output("")
            self.add_output(msg)
    
    def _systemctl_stop(self, service_name):
        """Stop a systemd service"""
        success, message = self.systemd_manager.stop_service(service_name)
        self.add_output(message)
        self.add_output("")
    
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
