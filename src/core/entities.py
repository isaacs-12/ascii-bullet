"""
Game entities - player, enemies, bullets
"""


class Entity:
    """Base class for all game entities"""
    
    def __init__(self, x, y, char='@', color=None):
        """
        Initialize an entity
        
        Args:
            x: X position in world coordinates (cell units)
            y: Y position in world coordinates (cell units)
            char: ASCII character to display
            color: RGB color tuple
        """
        # Store position in sub-cell coordinates (4x4 subdivision)
        self.x = float(x * 4)
        self.y = float(y * 4)
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
    
    def get_cell_position(self):
        """Get position in cell coordinates for rendering"""
        return (self.x / 4.0, self.y / 4.0)
    
    def get_position(self):
        """Get integer position for rendering (legacy method)"""
        return self.get_cell_position()


class Player(Entity):
    """The player character"""
    
    def __init__(self, x, y):
        super().__init__(x, y, char='o', color=(0, 255, 0))
        self.speed = 12.0  # Cells per second (increased by 50% from 8.0)
        self.hitbox_radius = 0.3  # Small hitbox for bullet hell
        # Position is already in sub-cell coordinates from Entity.__init__
    
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
        # Normalize diagonal movement to maintain constant velocity
        if dx != 0 and dy != 0:
            # Diagonal: normalize to maintain same speed
            length = (dx**2 + dy**2) ** 0.5
            dx = dx / length
            dy = dy / length
        
        # Calculate movement in sub-cell units
        # speed is in cells/second, convert to sub-cells/second (multiply by 4)
        # But we want smaller steps, so we use the speed as-is in sub-cell units
        # Actually, if speed is 3.0 cells/sec, that's 12.0 sub-cells/sec
        move_distance = (self.speed * 4) * (dt / 1000.0)
        
        new_x = self.x + (dx * move_distance)
        new_y = self.y + (dy * move_distance)
        
        # Clamp to map boundaries (in sub-cell units)
        max_x = (map_width - 1) * 4
        max_y = (map_height - 1) * 4
        self.x = max(0, min(max_x, new_x))
        self.y = max(0, min(max_y, new_y))
    
    def get_cell_position(self):
        """Get position in cell coordinates for rendering"""
        return (self.x / 4.0, self.y / 4.0)


class Bullet(Entity):
    """A bullet/projectile"""
    
    def __init__(self, x, y, vx, vy, char='.', color=(255, 100, 100)):
        """
        Initialize a bullet
        
        Args:
            x: Starting X position (cell units)
            y: Starting Y position (cell units)
            vx: X velocity in cells per second
            vy: Y velocity in cells per second
            char: Display character
            color: RGB color
        """
        super().__init__(x, y, char=char, color=color)
        # Convert velocity to sub-cell units (multiply by 4)
        self.vx = vx * 4
        self.vy = vy * 4
    
    def update(self, dt):
        """Update bullet position"""
        # Move based on velocity (in sub-cell units)
        self.x += self.vx * (dt / 1000.0)
        self.y += self.vy * (dt / 1000.0)
    
    def is_off_map(self, map_width, map_height):
        """Check if bullet is off the map (same boundaries as player)"""
        cell_x, cell_y = self.get_cell_position()
        # Use same boundaries as player: 0 to map_width-1, 0 to map_height-1
        # Add small buffer (-1) for bullets that are just leaving the map
        # But clamp upper bound to match player's max position (map_width-1, map_height-1)
        return (cell_x < -1 or cell_x >= map_width or
                cell_y < -1 or cell_y >= map_height)


class Enemy(Entity):
    """Base enemy class"""
    
    def __init__(self, x, y, char='X', color=(255, 0, 0), bullet_speed=10.0, movement_speed=2.0, movement_type='basic'):
        super().__init__(x, y, char=char, color=color)
        self.fire_cooldown = 0
        self.fire_rate = 1000  # Milliseconds between shots
        self.bullet_speed = bullet_speed  # Speed of bullets this enemy fires
        self.movement_speed = movement_speed  # Movement speed in cells per second
        self.movement_type = movement_type  # 'basic', 'erratic', 'maintain_distance', 'chase'
        
        # Movement direction (random initial direction)
        import random
        angle = random.uniform(0, 2 * 3.14159)
        self.vx = movement_speed * (angle / 3.14159 - 1)  # Simplistic direction
        self.vy = movement_speed * (1 - abs(self.vx) / movement_speed)
        
        # For erratic movement
        self.direction_change_timer = 0
        self.direction_change_interval = random.uniform(500, 2000)  # Change direction every 0.5-2 seconds
        
        # For maintain_distance movement
        self.preferred_distance = random.uniform(8, 15)  # Preferred distance from player
        
        # Health/ammo (each shot costs health)
        self.health = 20  # 20 shots worth of health
    
    def update(self, dt, map_width, map_height, player=None):
        """Update enemy state and movement"""
        if self.fire_cooldown > 0:
            self.fire_cooldown -= dt
        
        # Update movement based on type
        if self.movement_type == 'erratic':
            self._update_erratic_movement(dt)
        elif self.movement_type == 'maintain_distance' and player:
            self._update_maintain_distance_movement(dt, player)
        elif self.movement_type == 'chase' and player:
            self._update_chase_movement(dt, player)
        else:
            self._update_basic_movement(dt)
        
        # Move enemy (convert speed to sub-cell units)
        move_dist = (self.movement_speed * 4) * (dt / 1000.0)
        # Normalize velocity vector
        v_length = (self.vx**2 + self.vy**2) ** 0.5
        if v_length > 0:
            self.x += (self.vx / v_length) * move_dist
            self.y += (self.vy / v_length) * move_dist
        
        # Bounce off walls (check in cell coordinates)
        cell_x, cell_y = self.get_cell_position()
        max_x = (map_width - 1) * 4
        max_y = (map_height - 1) * 4
        
        if cell_x <= 1:
            self.vx = abs(self.vx)
            self.x = 1 * 4
        elif cell_x >= map_width - 1:
            self.vx = -abs(self.vx)
            self.x = (map_width - 1) * 4
        if cell_y <= 1:
            self.vy = abs(self.vy)
            self.y = 1 * 4
        elif cell_y >= map_height - 1:
            self.vy = -abs(self.vy)
            self.y = (map_height - 1) * 4
    
    def _update_basic_movement(self, dt):
        """Basic movement - continues in current direction"""
        pass  # Velocity already set
    
    def _update_erratic_movement(self, dt):
        """Erratic movement - randomly changes direction"""
        import random
        self.direction_change_timer += dt
        if self.direction_change_timer >= self.direction_change_interval:
            self.direction_change_timer = 0
            self.direction_change_interval = random.uniform(500, 2000)
            # Random new direction
            angle = random.uniform(0, 2 * 3.14159)
            speed = (self.vx**2 + self.vy**2) ** 0.5
            self.vx = speed * (angle / 3.14159 - 1)
            self.vy = speed * (1 - abs(self.vx) / speed) if speed > 0 else 0
    
    def _update_maintain_distance_movement(self, dt, player):
        """Maintain a preferred distance from player"""
        px, py = player.get_cell_position()
        ex, ey = self.get_cell_position()
        
        dx = px - ex
        dy = py - ey
        distance = (dx**2 + dy**2) ** 0.5
        
        if distance > 0:
            # Normalize direction
            dx_norm = dx / distance
            dy_norm = dy / distance
            
            # If too close, move away; if too far, move closer
            if distance < self.preferred_distance:
                # Move away from player
                self.vx = -dx_norm * self.movement_speed
                self.vy = -dy_norm * self.movement_speed
            elif distance > self.preferred_distance * 1.5:
                # Move towards player
                self.vx = dx_norm * self.movement_speed
                self.vy = dy_norm * self.movement_speed
            else:
                # At preferred distance - move perpendicular
                self.vx = -dy_norm * self.movement_speed
                self.vy = dx_norm * self.movement_speed
    
    def _update_chase_movement(self, dt, player):
        """Chase the player"""
        px, py = player.get_cell_position()
        ex, ey = self.get_cell_position()
        
        dx = px - ex
        dy = py - ey
        distance = (dx**2 + dy**2) ** 0.5
        
        if distance > 0:
            # Normalize and set velocity towards player
            self.vx = (dx / distance) * self.movement_speed
            self.vy = (dy / distance) * self.movement_speed
    
    def can_fire(self):
        """Check if enemy can fire"""
        return self.fire_cooldown <= 0
    
    def fire(self, target_x, target_y):
        """
        Fire a bullet towards a target (costs health)
        
        Args:
            target_x: Target X position (cell units)
            target_y: Target Y position (cell units)
            
        Returns:
            Bullet instance or None
        """
        if not self.can_fire() or self.health <= 0:
            return None
        
        # Get enemy position in cell coordinates
        ex, ey = self.get_cell_position()
        
        # Calculate direction to target
        dx = target_x - ex
        dy = target_y - ey
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
            
            # Bullet inherits enemy's color (pass cell coordinates)
            return Bullet(ex, ey, vx, vy, color=self.color)
        
        return None

