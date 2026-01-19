"""
Terminal-style renderer for the game
Provides a retro ASCII terminal aesthetic
"""

import os
import sys
import pygame


class TerminalRenderer:
    """Handles rendering with a terminal-like appearance"""
    
    # Terminal color scheme
    COLORS = {
        'bg': (10, 10, 15),           # Dark background
        'fg': (0, 255, 0),            # Bright green text
        'title_bar': (15, 15, 20),    # Title bar background
        'menu_selected': (0, 255, 0),  # Selected menu item
        'menu_normal': (120, 255, 120), # Normal menu item
        'title': (100, 255, 100),     # Title text
    }
    
    def __init__(self, width=80, height=50, cell_size=12):
        """
        Initialize the terminal renderer
        
        Args:
            width: Initial number of character columns
            height: Initial number of character rows
            cell_size: Size of each character cell in pixels
        """
        # Store initial dimensions
        self.initial_width = width
        self.initial_height = height
        self.font_size = cell_size
        
        # Initialize pygame first
        pygame.init()
        
        # Load monospace font and get actual character metrics
        self.font = pygame.font.Font(pygame.font.match_font('courier', bold=True), cell_size)
        self.title_font = pygame.font.Font(pygame.font.match_font('courier', bold=True), 10)
        
        # Get actual character dimensions from font metrics
        # Test with a wide character to ensure proper spacing
        test_char = self.font.render('█', True, (255, 255, 255))
        self.char_pixel_width = test_char.get_width()
        self.char_pixel_height = self.font.get_height()
        
        # Use actual character width for cell spacing
        self.cell_width = self.char_pixel_width
        self.cell_height = self.char_pixel_height
        
        # Frame settings
        self.frame_thickness = 0  # No border frame
        self.title_bar_height = 20
        
        # Calculate initial window size
        self.char_width = width
        self.char_height = height
        self._calculate_window_dimensions()
        
        # Create the resizable display
        self.screen = pygame.display.set_mode(
            (self.window_width, self.window_height),
            pygame.RESIZABLE
        )
        pygame.display.set_caption("BULLET HELL TERMINAL")
        
        # Set window icon
        # Handle both development and PyInstaller bundled environments
        try:
            if getattr(sys, 'frozen', False):
                # Running in a PyInstaller bundle
                base_path = sys._MEIPASS
            else:
                # Running in development
                base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            icon_path = os.path.join(base_path, "src", "assets", "bllthll.png")
            if os.path.exists(icon_path):
                icon = pygame.image.load(icon_path)
                pygame.display.set_icon(icon)
        except (pygame.error, FileNotFoundError, AttributeError):
            # If icon file doesn't exist, continue without it
            pass
        
        # Create buffer for terminal content
        self._resize_buffer(width, height)
        
        self.clock = pygame.time.Clock()
    
    def _calculate_window_dimensions(self):
        """Calculate window dimensions based on character grid size"""
        self.terminal_width = self.char_width * self.cell_width
        self.terminal_height = self.char_height * self.cell_height
        self.window_width = self.terminal_width + (self.frame_thickness * 2)
        self.window_height = self.terminal_height + (self.frame_thickness * 2) + self.title_bar_height
    
    def _resize_buffer(self, new_width, new_height):
        """
        Resize the terminal buffer, preserving existing content where possible
        
        Args:
            new_width: New number of columns
            new_height: New number of rows
        """
        old_buffer = getattr(self, 'buffer', None)
        old_color_buffer = getattr(self, 'color_buffer', None)
        
        # Create new buffers
        self.buffer = [[' ' for _ in range(new_width)] for _ in range(new_height)]
        self.color_buffer = [[self.COLORS['fg'] for _ in range(new_width)] for _ in range(new_height)]
        
        # Copy old content if it exists
        if old_buffer:
            old_height = len(old_buffer)
            old_width = len(old_buffer[0]) if old_height > 0 else 0
            
            for row in range(min(old_height, new_height)):
                for col in range(min(old_width, new_width)):
                    self.buffer[row][col] = old_buffer[row][col]
                    self.color_buffer[row][col] = old_color_buffer[row][col]
    
    def handle_resize(self, new_width, new_height):
        """
        Handle window resize event (called by pygame event handler)
        
        Args:
            new_width: New window width in pixels
            new_height: New window height in pixels
        """
        # Just recreate the surface - actual size calculations happen in render()
        self.screen = pygame.display.set_mode((new_width, new_height), pygame.RESIZABLE)
    
    def clear(self):
        """Clear the terminal buffer"""
        for row in range(self.char_height):
            for col in range(self.char_width):
                self.buffer[row][col] = ' '
                self.color_buffer[row][col] = self.COLORS['fg']
    
    def write(self, x, y, text, color=None):
        """
        Write text to the terminal buffer
        
        Args:
            x: Column position
            y: Row position
            text: Text to write
            color: Text color (defaults to fg color)
        """
        if color is None:
            color = self.COLORS['fg']
        
        for i, char in enumerate(text):
            col = x + i
            if 0 <= y < self.char_height and 0 <= col < self.char_width:
                self.buffer[y][col] = char
                self.color_buffer[y][col] = color
    
    def write_centered(self, y, text, color=None):
        """Write text centered on the given row"""
        x = (self.char_width - len(text)) // 2
        self.write(x, y, text, color)
    
    def draw_box(self, x, y, width, height, color=None):
        """Draw a box using ASCII characters"""
        if color is None:
            color = self.COLORS['fg']
        
        # Corners and edges
        self.write(x, y, '+' + '-' * (width - 2) + '+', color)
        self.write(x, y + height - 1, '+' + '-' * (width - 2) + '+', color)
        
        for row in range(y + 1, y + height - 1):
            self.write(x, row, '|', color)
            self.write(x + width - 1, row, '|', color)
    
    def render(self):
        """Render the terminal to the screen"""
        # Get CURRENT window size every frame (works during resize drag)
        actual_width, actual_height = self.screen.get_size()
        
        # Calculate character grid dimensions from current window size
        available_width = actual_width - (self.frame_thickness * 2)
        available_height = actual_height - (self.frame_thickness * 2) - self.title_bar_height
        
        current_char_width = max(20, available_width // self.cell_width)
        current_char_height = max(10, available_height // self.cell_height)
        
        # Calculate exact terminal dimensions for this grid
        current_terminal_width = current_char_width * self.cell_width
        current_terminal_height = current_char_height * self.cell_height
        
        # Update buffer if grid size changed
        if current_char_width != self.char_width or current_char_height != self.char_height:
            self.char_width = current_char_width
            self.char_height = current_char_height
            self.terminal_width = current_terminal_width
            self.terminal_height = current_terminal_height
            self.window_width = actual_width
            self.window_height = actual_height
            self._resize_buffer(current_char_width, current_char_height)
        
        # Fill background with terminal color
        self.screen.fill(self.COLORS['bg'])
        
        # Draw title bar
        title_bar_rect = pygame.Rect(0, 0, actual_width, self.title_bar_height)
        pygame.draw.rect(self.screen, self.COLORS['title_bar'], title_bar_rect)
        
        title_surface = self.title_font.render("● ASCII BULLET HELL", True, self.COLORS['menu_normal'])
        self.screen.blit(title_surface, (8, 5))
        
        # Add size indicator in title bar
        size_text = f"{current_char_width}x{current_char_height}"
        size_surface = self.title_font.render(size_text, True, self.COLORS['menu_normal'])
        self.screen.blit(size_surface, (actual_width - size_surface.get_width() - 8, 5))
        
        # Create a separate surface for terminal content at exact calculated size
        terminal_surface = pygame.Surface((current_terminal_width, current_terminal_height))
        terminal_surface.fill(self.COLORS['bg'])
        
        # Draw buffer contents to the terminal surface
        if self.buffer and len(self.buffer) > 0:
            for row in range(min(current_char_height, len(self.buffer))):
                if row < len(self.buffer):
                    for col in range(min(current_char_width, len(self.buffer[row]))):
                        if col < len(self.buffer[row]):
                            char = self.buffer[row][col]
                            if char != ' ':
                                color = self.color_buffer[row][col]
                                try:
                                    char_surface = self.font.render(char, True, color)
                                except (pygame.error, UnicodeError):
                                    # Fallback for characters the font can't render (e.g., emoji)
                                    char_surface = self.font.render('?', True, color)
                                x = col * self.cell_width
                                y = row * self.cell_height
                                terminal_surface.blit(char_surface, (x, y))
        
        # Blit the terminal surface to the screen
        terminal_pos = (self.frame_thickness, self.title_bar_height + self.frame_thickness)
        self.screen.blit(terminal_surface, terminal_pos)
        
        pygame.display.flip()
    
    def tick(self, fps=60):
        """Update the clock"""
        return self.clock.tick(fps)
    
    def quit(self):
        """Clean up and quit pygame"""
        pygame.quit()

