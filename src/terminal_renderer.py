"""
Terminal-style renderer for the game
Provides a retro ASCII terminal aesthetic
"""

import pygame


class TerminalRenderer:
    """Handles rendering with a terminal-like appearance"""
    
    # Terminal color scheme
    COLORS = {
        'bg': (10, 10, 15),           # Dark background
        'fg': (0, 255, 0),            # Bright green text
        'frame': (40, 40, 50),        # Frame color
        'frame_highlight': (60, 60, 80),  # Frame highlight
        'menu_selected': (0, 255, 0),  # Selected menu item
        'menu_normal': (120, 255, 120), # Normal menu item
        'title': (100, 255, 100),     # Title text
    }
    
    def __init__(self, width=80, height=50, cell_size=12):
        """
        Initialize the terminal renderer
        
        Args:
            width: Number of character columns
            height: Number of character rows
            cell_size: Size of each character cell in pixels
        """
        self.char_width = width
        self.char_height = height
        self.cell_size = cell_size
        
        # Calculate window size with frame
        self.frame_thickness = 20
        self.terminal_width = width * cell_size
        self.terminal_height = height * cell_size
        self.window_width = self.terminal_width + (self.frame_thickness * 2)
        self.window_height = self.terminal_height + (self.frame_thickness * 2) + 30  # Extra for title bar
        
        # Initialize pygame
        pygame.init()
        self.screen = pygame.display.set_mode((self.window_width, self.window_height))
        pygame.display.set_caption("ASCII BULLET HELL")
        
        # Load monospace font
        self.font = pygame.font.Font(pygame.font.match_font('courier', bold=True), cell_size)
        self.title_font = pygame.font.Font(pygame.font.match_font('courier', bold=True), 16)
        
        # Create buffer for terminal content
        self.buffer = [[' ' for _ in range(width)] for _ in range(height)]
        self.color_buffer = [[self.COLORS['fg'] for _ in range(width)] for _ in range(height)]
        
        self.clock = pygame.time.Clock()
    
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
        self.write(x, y, '┌' + '─' * (width - 2) + '┐', color)
        self.write(x, y + height - 1, '└' + '─' * (width - 2) + '┘', color)
        
        for row in range(y + 1, y + height - 1):
            self.write(x, row, '│', color)
            self.write(x + width - 1, row, '│', color)
    
    def render(self):
        """Render the terminal to the screen"""
        # Fill background
        self.screen.fill(self.COLORS['frame'])
        
        # Draw title bar
        title_bar_rect = pygame.Rect(0, 0, self.window_width, 30)
        pygame.draw.rect(self.screen, self.COLORS['frame_highlight'], title_bar_rect)
        
        title_surface = self.title_font.render("● ASCII BULLET HELL", True, self.COLORS['menu_normal'])
        self.screen.blit(title_surface, (10, 7))
        
        # Draw frame with 3D effect
        terminal_rect = pygame.Rect(
            self.frame_thickness,
            30 + self.frame_thickness,
            self.terminal_width,
            self.terminal_height
        )
        
        # Outer shadow
        shadow_rect = terminal_rect.copy()
        shadow_rect.inflate_ip(4, 4)
        pygame.draw.rect(self.screen, (0, 0, 0), shadow_rect)
        
        # Terminal background
        pygame.draw.rect(self.screen, self.COLORS['bg'], terminal_rect)
        
        # Draw buffer contents
        for row in range(self.char_height):
            for col in range(self.char_width):
                char = self.buffer[row][col]
                if char != ' ':
                    color = self.color_buffer[row][col]
                    char_surface = self.font.render(char, True, color)
                    x = self.frame_thickness + (col * self.cell_size)
                    y = 30 + self.frame_thickness + (row * self.cell_size)
                    self.screen.blit(char_surface, (x, y))
        
        pygame.display.flip()
    
    def tick(self, fps=60):
        """Update the clock"""
        return self.clock.tick(fps)
    
    def quit(self):
        """Clean up and quit pygame"""
        pygame.quit()

