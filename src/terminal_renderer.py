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
        self.title_font = pygame.font.Font(pygame.font.match_font('courier', bold=True), 16)
        
        # Get actual character dimensions from font metrics
        # Test with a wide character to ensure proper spacing
        test_char = self.font.render('█', True, (255, 255, 255))
        self.char_pixel_width = test_char.get_width()
        self.char_pixel_height = self.font.get_height()
        
        # Use actual character width for cell spacing
        self.cell_width = self.char_pixel_width
        self.cell_height = self.char_pixel_height
        
        # Frame settings
        self.frame_thickness = 20
        self.title_bar_height = 30
        
        # Calculate initial window size
        self.char_width = width
        self.char_height = height
        self._calculate_window_dimensions()
        
        # Create the resizable display
        self.screen = pygame.display.set_mode(
            (self.window_width, self.window_height),
            pygame.RESIZABLE
        )
        pygame.display.set_caption("ASCII BULLET HELL")
        
        # Create buffer for terminal content
        self._resize_buffer(width, height)
        
        # Track last known window size for live resize detection
        self.last_window_size = (self.window_width, self.window_height)
        
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
        Handle window resize event
        
        Args:
            new_width: New window width in pixels
            new_height: New window height in pixels
        """
        # Accept whatever size the OS gives us (especially during drag)
        self.window_width = new_width
        self.window_height = new_height
        
        # Recreate the surface at the new size
        self.screen = pygame.display.set_mode((new_width, new_height), pygame.RESIZABLE)
        self.last_window_size = (new_width, new_height)
        
        # Calculate how many characters can fit in the available space
        available_width = new_width - (self.frame_thickness * 2)
        available_height = new_height - (self.frame_thickness * 2) - self.title_bar_height
        
        new_char_width = max(20, available_width // self.cell_width)  # Minimum 20 columns
        new_char_height = max(10, available_height // self.cell_height)  # Minimum 10 rows
        
        # Calculate exact terminal size for this character grid
        self.terminal_width = new_char_width * self.cell_width
        self.terminal_height = new_char_height * self.cell_height
        
        # Update character dimensions and resize buffer if needed
        if new_char_width != self.char_width or new_char_height != self.char_height:
            self.char_width = new_char_width
            self.char_height = new_char_height
            
            # Resize buffer to match new character grid
            self._resize_buffer(new_char_width, new_char_height)
    
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
    
    def check_resize(self):
        """Check if window was resized and update accordingly"""
        current_size = self.screen.get_size()
        if current_size != self.last_window_size:
            self.handle_resize(current_size[0], current_size[1])
            self.last_window_size = current_size
    
    def render(self):
        """Render the terminal to the screen"""
        # Check for live resize (during drag operations)
        self.check_resize()
        
        # Fill background
        self.screen.fill(self.COLORS['frame'])
        
        # Draw title bar
        title_bar_rect = pygame.Rect(0, 0, self.window_width, self.title_bar_height)
        pygame.draw.rect(self.screen, self.COLORS['frame_highlight'], title_bar_rect)
        
        title_surface = self.title_font.render("● ASCII BULLET HELL", True, self.COLORS['menu_normal'])
        self.screen.blit(title_surface, (10, 7))
        
        # Add size indicator in title bar
        size_text = f"{self.char_width}x{self.char_height}"
        size_surface = self.title_font.render(size_text, True, self.COLORS['menu_normal'])
        self.screen.blit(size_surface, (self.window_width - size_surface.get_width() - 10, 7))
        
        # Draw frame with 3D effect
        terminal_rect = pygame.Rect(
            self.frame_thickness,
            self.title_bar_height + self.frame_thickness,
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
                    x = self.frame_thickness + (col * self.cell_width)
                    y = self.title_bar_height + self.frame_thickness + (row * self.cell_height)
                    self.screen.blit(char_surface, (x, y))
        
        pygame.display.flip()
    
    def tick(self, fps=60):
        """Update the clock"""
        return self.clock.tick(fps)
    
    def quit(self):
        """Clean up and quit pygame"""
        pygame.quit()

