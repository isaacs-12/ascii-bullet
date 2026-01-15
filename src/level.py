"""
Level configuration and generation system
"""

import random
from src.entities import Enemy


class LevelConfig:
    """Configuration for a level"""
    
    def __init__(self, width=100, height=60, seed=None):
        """
        Initialize level configuration
        
        Args:
            width: Map width in cells
            height: Map height in cells
            seed: Random seed for reproducible generation
        """
        self.width = width
        self.height = height
        self.seed = seed
        
        # Enemy spawn configuration
        self.min_enemies = 3
        self.max_enemies = 8
        self.enemy_types = ['basic', 'fast', 'sniper']
        
        # Difficulty modifiers
        self.enemy_fire_rate_multiplier = 1.0
        self.bullet_speed_multiplier = 1.0


class Level:
    """A game level with entities and configuration"""
    
    def __init__(self, config):
        """
        Initialize a level
        
        Args:
            config: LevelConfig instance
        """
        self.config = config
        self.width = config.width
        self.height = config.height
        self.enemies = []
        self.bullets = []
        
        # Set random seed if provided
        if config.seed is not None:
            random.seed(config.seed)
        
        # Generate level
        self._generate_enemies()
    
    def _generate_enemies(self):
        """Generate enemies based on configuration"""
        num_enemies = random.randint(self.config.min_enemies, self.config.max_enemies)
        
        for _ in range(num_enemies):
            # Random position (avoid edges where player starts)
            x = random.uniform(self.width * 0.3, self.width * 0.9)
            y = random.uniform(self.height * 0.2, self.height * 0.8)
            
            # Choose enemy type
            enemy_type = random.choice(self.config.enemy_types)
            enemy = self._create_enemy(enemy_type, x, y)
            
            if enemy:
                self.enemies.append(enemy)
    
    def _create_enemy(self, enemy_type, x, y):
        """
        Create an enemy of the specified type
        
        Args:
            enemy_type: Type of enemy ('basic', 'fast', 'sniper')
            x: X position
            y: Y position
            
        Returns:
            Enemy instance
        """
        if enemy_type == 'basic':
            # Red - moderate speed and fire rate
            enemy = Enemy(x, y, char='X', color=(255, 100, 100), bullet_speed=12.0)
            enemy.fire_rate = 2000  # Fire every 2 seconds
            
        elif enemy_type == 'fast':
            # Orange - fast firing, medium bullet speed
            enemy = Enemy(x, y, char='X', color=(255, 150, 0), bullet_speed=10.0)
            enemy.fire_rate = 1000  # Fire every second
            
        elif enemy_type == 'sniper':
            # Purple - slow firing, very fast bullets
            enemy = Enemy(x, y, char='X', color=(255, 0, 255), bullet_speed=18.0)
            enemy.fire_rate = 3000  # Fire every 3 seconds (but faster bullets)
        
        else:
            enemy = Enemy(x, y)
        
        # Apply difficulty multipliers
        enemy.fire_rate = int(enemy.fire_rate / self.config.enemy_fire_rate_multiplier)
        enemy.bullet_speed *= self.config.bullet_speed_multiplier
        
        return enemy
    
    def update(self, dt, player):
        """
        Update level entities
        
        Args:
            dt: Delta time in milliseconds
            player: Player entity
        """
        # Update enemies
        for enemy in self.enemies:
            enemy.update(dt)
            
            # Try to fire at player
            bullet = enemy.fire(player.x, player.y)
            if bullet:
                self.bullets.append(bullet)
        
        # Update bullets
        for bullet in self.bullets:
            bullet.update(dt)
        
        # Remove bullets that are off map
        self.bullets = [b for b in self.bullets 
                       if not b.is_off_map(self.width, self.height)]
    
    def check_collisions(self, player):
        """
        Check if player collides with any bullets
        
        Args:
            player: Player entity
            
        Returns:
            bool: True if player was hit
        """
        for bullet in self.bullets:
            # Simple distance check
            dx = player.x - bullet.x
            dy = player.y - bullet.y
            distance = (dx**2 + dy**2) ** 0.5
            
            if distance < player.hitbox_radius:
                return True
        
        return False
    
    def get_entities(self):
        """Get all entities for rendering"""
        return self.enemies + self.bullets


# Predefined level configurations
LEVEL_1 = LevelConfig(
    width=80,
    height=50,
    seed=12345
)
LEVEL_1.min_enemies = 3
LEVEL_1.max_enemies = 5
LEVEL_1.enemy_fire_rate_multiplier = 0.8

LEVEL_2 = LevelConfig(
    width=120,
    height=70,
    seed=67890
)
LEVEL_2.min_enemies = 5
LEVEL_2.max_enemies = 10
LEVEL_2.enemy_fire_rate_multiplier = 1.2

