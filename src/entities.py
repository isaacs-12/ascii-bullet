"""
Game entities - player, enemies, bullets
"""


class Entity:
    """Base class for all game entities"""
    
    def __init__(self, x, y, char='@', color=None):
        """
        Initialize an entity
        
        Args:
            x: X position in world coordinates
            y: Y position in world coordinates
            char: ASCII character to display
            color: RGB color tuple
        """
        self.x = float(x)
        self.y = float(y)
        self.char = char
        self.color = color
        self.alive = True
    
    def update(self, dt):
        """
        Update entity state
        
        Args:
            dt: Delta time in milliseconds
        """
        pass
    
    def get_position(self):
        """Get integer position for rendering"""
        return (int(self.x), int(self.y))


class Player(Entity):
    """The player character"""
    
    def __init__(self, x, y):
        super().__init__(x, y, char='o', color=(0, 255, 0))
        self.speed = 8.0  # Cells per second
        self.hitbox_radius = 0.3  # Small hitbox for bullet hell
    
    def move(self, dx, dy, dt, map_width, map_height):
        """
        Move the player
        
        Args:
            dx: X direction (-1, 0, or 1)
            dy: Y direction (-1, 0, or 1)
            dt: Delta time in milliseconds
            map_width: Map width in cells
            map_height: Map height in cells
        """
        # Calculate movement
        move_distance = self.speed * (dt / 1000.0)
        
        new_x = self.x + (dx * move_distance)
        new_y = self.y + (dy * move_distance)
        
        # Clamp to map boundaries
        self.x = max(0, min(map_width - 1, new_x))
        self.y = max(0, min(map_height - 1, new_y))


class Bullet(Entity):
    """A bullet/projectile"""
    
    def __init__(self, x, y, vx, vy, char='.', color=(255, 100, 100)):
        """
        Initialize a bullet
        
        Args:
            x: Starting X position
            y: Starting Y position
            vx: X velocity in cells per second
            vy: Y velocity in cells per second
            char: Display character
            color: RGB color
        """
        super().__init__(x, y, char=char, color=color)
        self.vx = vx
        self.vy = vy
    
    def update(self, dt):
        """Update bullet position"""
        # Move based on velocity
        self.x += self.vx * (dt / 1000.0)
        self.y += self.vy * (dt / 1000.0)
    
    def is_off_map(self, map_width, map_height):
        """Check if bullet is off the map"""
        return (self.x < -5 or self.x > map_width + 5 or
                self.y < -5 or self.y > map_height + 5)


class Enemy(Entity):
    """Base enemy class"""
    
    def __init__(self, x, y, char='X', color=(255, 0, 0), bullet_speed=10.0, movement_speed=2.0):
        super().__init__(x, y, char=char, color=color)
        self.fire_cooldown = 0
        self.fire_rate = 1000  # Milliseconds between shots
        self.bullet_speed = bullet_speed  # Speed of bullets this enemy fires
        self.movement_speed = movement_speed  # Movement speed in cells per second
        
        # Movement direction (random initial direction)
        import random
        angle = random.uniform(0, 2 * 3.14159)
        self.vx = movement_speed * (angle / 3.14159 - 1)  # Simplistic direction
        self.vy = movement_speed * (1 - abs(self.vx) / movement_speed)
        
        # Health/ammo (each shot costs health)
        self.health = 20  # 20 shots worth of health
    
    def update(self, dt, map_width, map_height):
        """Update enemy state and movement"""
        if self.fire_cooldown > 0:
            self.fire_cooldown -= dt
        
        # Move enemy
        move_dist = self.movement_speed * (dt / 1000.0)
        self.x += self.vx * (move_dist / self.movement_speed)
        self.y += self.vy * (move_dist / self.movement_speed)
        
        # Bounce off walls
        if self.x <= 1 or self.x >= map_width - 1:
            self.vx = -self.vx
            self.x = max(1, min(map_width - 1, self.x))
        if self.y <= 1 or self.y >= map_height - 1:
            self.vy = -self.vy
            self.y = max(1, min(map_height - 1, self.y))
    
    def can_fire(self):
        """Check if enemy can fire"""
        return self.fire_cooldown <= 0
    
    def fire(self, target_x, target_y):
        """
        Fire a bullet towards a target (costs health)
        
        Args:
            target_x: Target X position
            target_y: Target Y position
            
        Returns:
            Bullet instance or None
        """
        if not self.can_fire() or self.health <= 0:
            return None
        
        # Calculate direction to target
        dx = target_x - self.x
        dy = target_y - self.y
        dist = (dx**2 + dy**2) ** 0.5
        
        if dist > 0:
            # Normalize and set bullet speed (use enemy's bullet_speed)
            vx = (dx / dist) * self.bullet_speed
            vy = (dy / dist) * self.bullet_speed
            
            self.fire_cooldown = self.fire_rate
            # Shooting costs health
            self.health -= 1
            
            # Enemy dies if out of health
            if self.health <= 0:
                self.alive = False
            
            # Bullet inherits enemy's color
            return Bullet(self.x, self.y, vx, vy, color=self.color)
        
        return None

