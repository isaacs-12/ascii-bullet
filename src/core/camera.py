"""
Camera/Viewport system for game rendering
"""


class Camera:
    """Manages viewport and camera positioning"""
    
    def __init__(self, viewport_width, viewport_height, map_width, map_height):
        """
        Initialize the camera
        
        Args:
            viewport_width: Width of viewport in cells
            viewport_height: Height of viewport in cells
            map_width: Total map width in cells
            map_height: Total map height in cells
        """
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.map_width = map_width
        self.map_height = map_height
        
        # Camera position (top-left corner of viewport in world space)
        self.x = 0
        self.y = 0
    
    def update(self, player_x, player_y):
        """
        Update camera position to follow player
        
        Args:
            player_x: Player X position in world coordinates
            player_y: Player Y position in world coordinates
        """
        # Try to center player in viewport
        target_x = player_x - self.viewport_width // 2
        target_y = player_y - self.viewport_height // 2
        
        # Clamp camera to map boundaries
        self.x = max(0, min(target_x, self.map_width - self.viewport_width))
        self.y = max(0, min(target_y, self.map_height - self.viewport_height))
        
        # Handle case where viewport is larger than map
        if self.viewport_width >= self.map_width:
            self.x = -(self.viewport_width - self.map_width) // 2
        if self.viewport_height >= self.map_height:
            self.y = -(self.viewport_height - self.map_height) // 2
    
    def world_to_screen(self, world_x, world_y):
        """
        Convert world coordinates to screen coordinates
        
        Args:
            world_x: X position in world
            world_y: Y position in world
            
        Returns:
            tuple: (screen_x, screen_y) or None if off-screen
        """
        screen_x = int(world_x) - int(self.x)
        screen_y = int(world_y) - int(self.y)
        
        # Check if on screen
        if 0 <= screen_x < self.viewport_width and 0 <= screen_y < self.viewport_height:
            return (screen_x, screen_y)
        return None
    
    def is_visible(self, world_x, world_y):
        """Check if a world position is visible"""
        return self.world_to_screen(world_x, world_y) is not None
    
    def get_visible_bounds(self):
        """
        Get the world coordinates visible in viewport
        
        Returns:
            tuple: (min_x, min_y, max_x, max_y)
        """
        return (
            int(self.x),
            int(self.y),
            int(self.x) + self.viewport_width,
            int(self.y) + self.viewport_height
        )

