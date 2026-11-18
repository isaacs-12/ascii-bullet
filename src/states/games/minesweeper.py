"""
Minesweeper game state
"""

import random
import time

import pygame

from src.states.base_state import BaseState


class MinesweeperState(BaseState):
    """Minesweeper gameplay state"""

    # Grid dimensions
    GRID_WIDTH = 30
    GRID_HEIGHT = 16
    MINE_COUNT = 99

    # Tile states
    TILE_HIDDEN = 0
    TILE_REVEALED = 1
    TILE_FLAGGED = 2
    TILE_MINE = 3

    def __init__(self, game, previous_state):
        super().__init__(game)
        self.previous_state = previous_state

        # Create larger font for minesweeper (50% larger)
        original_font_size = self.renderer.font_size
        self.minesweeper_font_size = int(original_font_size * 1.5)
        self.minesweeper_font = pygame.font.Font(
            pygame.font.match_font('courier', bold=True),
            self.minesweeper_font_size
        )
        # Calculate character dimensions with larger font
        test_char = self.minesweeper_font.render('█', True, (255, 255, 255))
        self.tile_char_width = test_char.get_width()
        self.tile_char_height = self.minesweeper_font.get_height()

        # Tile spacing (1 character gap between tiles)
        self.tile_spacing = 1

        # Game state
        self.game_state = "playing"  # playing, won, lost
        self.game_start_time = time.time()
        self.first_click = True

        # Initialize grid
        self.grid = [[0 for _ in range(self.GRID_WIDTH)] for _ in range(self.GRID_HEIGHT)]
        self.tile_states = [[self.TILE_HIDDEN for _ in range(self.GRID_WIDTH)] for _ in range(self.GRID_HEIGHT)]
        self.mines = set()
        self.flagged = set()

        # Playtime tracking
        self.stats_recorded = False

    def _place_mines(self, exclude_x, exclude_y):
        """Place mines randomly, excluding the clicked tile and its neighbors"""
        # Exclude clicked tile and all neighbors
        exclude = set()
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                nx, ny = exclude_x + dx, exclude_y + dy
                if 0 <= nx < self.GRID_WIDTH and 0 <= ny < self.GRID_HEIGHT:
                    exclude.add((nx, ny))

        # Generate all possible positions
        positions = [(x, y) for x in range(self.GRID_WIDTH) for y in range(self.GRID_HEIGHT)]
        positions = [p for p in positions if p not in exclude]

        # Randomly select mine positions
        self.mines = set(random.sample(positions, self.MINE_COUNT))

        # Calculate numbers for each tile
        for y in range(self.GRID_HEIGHT):
            for x in range(self.GRID_WIDTH):
                if (x, y) not in self.mines:
                    count = self._count_adjacent_mines(x, y)
                    self.grid[y][x] = count

    def _count_adjacent_mines(self, x, y):
        """Count mines adjacent to a tile"""
        count = 0
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.GRID_WIDTH and 0 <= ny < self.GRID_HEIGHT:
                    if (nx, ny) in self.mines:
                        count += 1
        return count

    def _reveal_tile(self, x, y):
        """Reveal a tile and recursively reveal empty neighbors"""
        if not (0 <= x < self.GRID_WIDTH and 0 <= y < self.GRID_HEIGHT):
            return

        if self.tile_states[y][x] != self.TILE_HIDDEN:
            return

        # First click - place mines
        if self.first_click:
            self._place_mines(x, y)
            self.first_click = False

        # Check if it's a mine
        if (x, y) in self.mines:
            self.tile_states[y][x] = self.TILE_MINE
            self.game_state = "lost"
            return

        # Reveal the tile
        self.tile_states[y][x] = self.TILE_REVEALED

        # If empty, reveal neighbors
        if self.grid[y][x] == 0:
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    self._reveal_tile(x + dx, y + dy)

    def _check_win(self):
        """Check if all non-mine tiles are revealed"""
        for y in range(self.GRID_HEIGHT):
            for x in range(self.GRID_WIDTH):
                if (x, y) not in self.mines:
                    if self.tile_states[y][x] != self.TILE_REVEALED:
                        return False
        return True

    def handle_events(self, events):
        """Handle input events"""
        for event in events:
            if event.type == pygame.QUIT:
                self.game.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    # Return to main menu
                    self.game.change_state(self.previous_state)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if self.game_state != "playing":
                    continue

                # Get mouse position
                mouse_x, mouse_y = pygame.mouse.get_pos()

                # Account for title bar and frame
                title_bar_height = self.renderer.title_bar_height
                frame_thickness = self.renderer.frame_thickness
                mouse_y -= (title_bar_height + frame_thickness)
                mouse_x -= frame_thickness

                # Header uses standard font, takes 2 character rows
                char_width = self.renderer.char_pixel_width
                char_height = self.renderer.char_pixel_height
                header_height = 2 * char_height

                # Check if click is in header area
                if mouse_y < header_height:
                    continue

                # Convert mouse position to grid coordinates
                # Tiles are rendered at: screen_y = tile_char_y * char_pixel_height + title_bar + frame
                # Where tile_char_y = y * (1 + spacing) + 2
                # So for grid row y: screen_y = (y * 2 + 2) * char_height + title_bar + frame
                # Solving for y: y = ((screen_y - title_bar - frame) / char_height - 2) / 2

                # mouse_y is already adjusted for title_bar and frame
                # Convert to character grid row (in full grid, not content area)
                full_grid_char_y = mouse_y // char_height

                # Grid starts at character row 2 (after header)
                # Each tile row takes 2 character rows (with spacing=1)
                if full_grid_char_y < 2:
                    continue  # Click is in header

                # Convert to grid row: grid row 0 starts at char row 2
                grid_y = (full_grid_char_y - 2) // (1 + self.tile_spacing)

                # X coordinate: tiles are at x * (1 + spacing) character columns
                grid_x = mouse_x // char_width // (1 + self.tile_spacing)

                # Clamp to valid grid bounds
                if grid_x < 0 or grid_x >= self.GRID_WIDTH or grid_y < 0 or grid_y >= self.GRID_HEIGHT:
                    continue

                if 0 <= grid_x < self.GRID_WIDTH and 0 <= grid_y < self.GRID_HEIGHT:
                    # Check for shift+click (flag)
                    if pygame.key.get_pressed()[pygame.K_LSHIFT] or pygame.key.get_pressed()[pygame.K_RSHIFT]:
                        # Toggle flag
                        if (grid_x, grid_y) in self.flagged:
                            self.flagged.remove((grid_x, grid_y))
                            if self.tile_states[grid_y][grid_x] == self.TILE_FLAGGED:
                                self.tile_states[grid_y][grid_x] = self.TILE_HIDDEN
                        else:
                            if self.tile_states[grid_y][grid_x] == self.TILE_HIDDEN:
                                self.flagged.add((grid_x, grid_y))
                                self.tile_states[grid_y][grid_x] = self.TILE_FLAGGED
                    else:
                        # Reveal tile
                        if self.tile_states[grid_y][grid_x] != self.TILE_FLAGGED:
                            self._reveal_tile(grid_x, grid_y)

                            # Check if game is lost
                            if self.game_state == "lost":
                                self.game_end_time = time.time()
                            # Check win condition
                            elif self._check_win():
                                self.game_state = "won"
                                self.game_end_time = time.time()

    def update(self, dt):
        """Update game logic"""
        # Record stats when game ends
        if self.game_state in ["won", "lost"] and not self.stats_recorded:
            self.game.save_system.add_playtime(time.time() - self.game_start_time, "minesweeper")
            self.stats_recorded = True

    def render(self):
        """Render the game"""
        # Calculate elapsed time first
        if self.game_state == "playing":
            elapsed = int(time.time() - self.game_start_time)
        else:
            if hasattr(self, 'game_end_time'):
                elapsed = int(self.game_end_time - self.game_start_time)
            else:
                elapsed = int(time.time() - self.game_start_time)

        # Calculate remaining bombs
        remaining = self.MINE_COUNT - len(self.flagged)

        # Top row: counter, face, timer
        counter_str = f"{remaining:03d}"
        face_str = ":-)" if self.game_state != "lost" else ":-("
        timer_str = f"{elapsed:03d}"

        # Clear buffer first
        self.renderer.clear()

        # Display header
        self.renderer.write(0, 0, counter_str, (255, 0, 0))

        # Center the face
        face_x = (self.renderer.char_width - len(face_str)) // 2
        face_color = (0, 255, 0) if self.game_state != "lost" else (255, 0, 0)
        self.renderer.write(face_x, 0, face_str, face_color)

        # Timer on the right
        timer_x = self.renderer.char_width - len(timer_str)
        self.renderer.write(timer_x, 0, timer_str, (255, 255, 0))

        # Render the terminal buffer first (header only)
        # We need to render without flipping, then add our tiles, then flip once
        # Get the current screen state without flipping
        actual_width, actual_height = self.renderer.screen.get_size()

        # Calculate character grid dimensions
        available_width = actual_width - (self.renderer.frame_thickness * 2)
        available_height = actual_height - (self.renderer.frame_thickness * 2) - self.renderer.title_bar_height

        current_char_width = max(20, available_width // self.renderer.cell_width)
        current_char_height = max(10, available_height // self.renderer.cell_height)

        # Fill background
        self.renderer.screen.fill(self.renderer.COLORS['bg'])

        # Draw title bar
        title_bar_rect = pygame.Rect(0, 0, actual_width, self.renderer.title_bar_height)
        pygame.draw.rect(self.renderer.screen, self.renderer.COLORS['title_bar'], title_bar_rect)

        title_surface = self.renderer.title_font.render("● ASCII BULLET HELL", True, self.renderer.COLORS['menu_normal'])
        self.renderer.screen.blit(title_surface, (8, 5))

        # Add size indicator
        size_text = f"{current_char_width}x{current_char_height}"
        size_surface = self.renderer.title_font.render(size_text, True, self.renderer.COLORS['menu_normal'])
        self.renderer.screen.blit(size_surface, (actual_width - size_surface.get_width() - 8, 5))

        # Create terminal surface
        current_terminal_width = current_char_width * self.renderer.cell_width
        current_terminal_height = current_char_height * self.renderer.cell_height
        terminal_surface = pygame.Surface((current_terminal_width, current_terminal_height))
        terminal_surface.fill(self.renderer.COLORS['bg'])

        # Draw header from buffer to terminal surface
        if self.renderer.buffer and len(self.renderer.buffer) > 0:
            for row in range(min(2, len(self.renderer.buffer))):  # Only header rows
                if row < len(self.renderer.buffer):
                    for col in range(min(current_char_width, len(self.renderer.buffer[row]))):
                        if col < len(self.renderer.buffer[row]):
                            char = self.renderer.buffer[row][col]
                            if char != ' ':
                                color = self.renderer.color_buffer[row][col]
                                try:
                                    char_surface = self.renderer.font.render(char, True, color)
                                except (pygame.error, UnicodeError):
                                    char_surface = self.renderer.font.render('?', True, color)
                                x = col * self.renderer.cell_width
                                y = row * self.renderer.cell_height
                                terminal_surface.blit(char_surface, (x, y))

        # Blit terminal surface
        terminal_pos = (self.renderer.frame_thickness, self.renderer.title_bar_height + self.renderer.frame_thickness)
        self.renderer.screen.blit(terminal_surface, terminal_pos)

        # Now render all tiles directly with larger font (don't write to buffer)
        for y in range(self.GRID_HEIGHT):
            for x in range(self.GRID_WIDTH):
                # Calculate tile position with spacing in character grid
                tile_char_x = x * (1 + self.tile_spacing)
                tile_char_y = y * (1 + self.tile_spacing) + 2  # Leave space for header

                state = self.tile_states[y][x]

                if state == self.TILE_HIDDEN:
                    char = "#"
                    color = (150, 150, 150)
                elif state == self.TILE_FLAGGED:
                    char = "?"
                    color = (255, 0, 0)
                elif state == self.TILE_MINE:
                    char = "X"
                    color = (255, 0, 0)
                elif state == self.TILE_REVEALED:
                    count = self.grid[y][x]
                    if count == 0:
                        continue  # Skip empty tiles
                    char = str(count)
                    # Color based on number
                    if count == 1:
                        color = (0, 100, 255)  # Blue
                    elif count == 2:
                        color = (0, 255, 0)  # Green
                    elif count == 3:
                        color = (255, 0, 0)  # Red
                    elif count == 4:
                        color = (255, 165, 0)  # Orange
                    else:  # 5+
                        color = (139, 0, 0)  # Dark red
                else:
                    continue

                # Calculate screen position for larger font rendering
                # Account for terminal surface position
                screen_x = tile_char_x * self.renderer.char_pixel_width + self.renderer.frame_thickness
                screen_y = tile_char_y * self.renderer.char_pixel_height + self.renderer.title_bar_height + self.renderer.frame_thickness

                # Render with larger font directly to screen
                text_surface = self.minesweeper_font.render(char, True, color)
                self.renderer.screen.blit(text_surface, (screen_x, screen_y))

        # Show game over message (render directly to screen with standard font)
        if self.game_state == "won":
            center_y = (self.renderer.char_height + 2) // 2
            msg_y = center_y * self.renderer.char_pixel_height + self.renderer.title_bar_height + self.renderer.frame_thickness
            msg_surface1 = self.renderer.font.render("YOU WIN!", True, (0, 255, 0))
            msg_surface2 = self.renderer.font.render(f"Time: {elapsed} seconds", True, (255, 255, 255))
            msg_surface3 = self.renderer.font.render("Press ESC to return", True, (150, 150, 150))
            msg_x = (actual_width - msg_surface1.get_width()) // 2
            self.renderer.screen.blit(msg_surface1, (msg_x, msg_y))
            msg_x = (actual_width - msg_surface2.get_width()) // 2
            self.renderer.screen.blit(msg_surface2, (msg_x, msg_y + self.renderer.char_pixel_height))
            msg_x = (actual_width - msg_surface3.get_width()) // 2
            self.renderer.screen.blit(msg_surface3, (msg_x, msg_y + 2 * self.renderer.char_pixel_height))
        elif self.game_state == "lost":
            center_y = (self.renderer.char_height + 2) // 2
            msg_y = center_y * self.renderer.char_pixel_height + self.renderer.title_bar_height + self.renderer.frame_thickness
            msg_surface1 = self.renderer.font.render("GAME OVER", True, (255, 0, 0))
            msg_surface2 = self.renderer.font.render("Press ESC to return", True, (150, 150, 150))
            msg_x = (actual_width - msg_surface1.get_width()) // 2
            self.renderer.screen.blit(msg_surface1, (msg_x, msg_y))
            msg_x = (actual_width - msg_surface2.get_width()) // 2
            self.renderer.screen.blit(msg_surface2, (msg_x, msg_y + self.renderer.char_pixel_height))

        # Display controls at the bottom (only when playing)
        if self.game_state == "playing":
            controls_y = (current_char_height - 1) * self.renderer.char_pixel_height + self.renderer.title_bar_height + self.renderer.frame_thickness
            controls_text = "Click: Reveal | Shift+Click: Flag | ESC: Quit"
            controls_surface = self.renderer.font.render(controls_text, True, (150, 150, 150))
            controls_x = (actual_width - controls_surface.get_width()) // 2
            self.renderer.screen.blit(controls_surface, (controls_x, controls_y))

        # Update display (single flip at the end)
        pygame.display.flip()

    def enter(self):
        """Called when entering this state"""
        pass

    def exit(self):
        """Called when exiting this state"""
        if self.game_state == "lost" and not hasattr(self, 'game_end_time'):
            self.game_end_time = time.time()
