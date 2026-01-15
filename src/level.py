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
        self.spawn_interval = 5000  # ms between spawns
        self.max_active_enemies = 15  # Maximum enemies on screen at once
        
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
        
        # Spawn tracking
        self.spawn_timer = 0
        self.spawn_counter = 0  # For seed-based spawning
        
        # Set random seed if provided
        if config.seed is not None:
            random.seed(config.seed)
            self.initial_seed = config.seed
        else:
            self.initial_seed = None
        
        # Generate initial enemies
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
            enemy = Enemy(x, y, char='X', color=(255, 100, 100), 
                         bullet_speed=12.0, movement_speed=2.0)
            enemy.fire_rate = 2000  # Fire every 2 seconds
            enemy.health = 20
            
        elif enemy_type == 'fast':
            # Orange - fast firing, medium bullet speed, fast movement
            enemy = Enemy(x, y, char='X', color=(255, 150, 0), 
                         bullet_speed=10.0, movement_speed=4.0)
            enemy.fire_rate = 1000  # Fire every second
            enemy.health = 15  # Less health but shoots faster
            
        elif enemy_type == 'sniper':
            # Purple - slow firing, very fast bullets, slow movement
            enemy = Enemy(x, y, char='X', color=(255, 0, 255), 
                         bullet_speed=18.0, movement_speed=1.0)
            enemy.fire_rate = 3000  # Fire every 3 seconds (but faster bullets)
            enemy.health = 10  # Low ammo, powerful shots
        
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
            enemy.update(dt, self.width, self.height)
            
            # Try to fire at player
            bullet = enemy.fire(player.x, player.y)
            if bullet:
                self.bullets.append(bullet)
        
        # Remove dead enemies (out of health)
        self.enemies = [e for e in self.enemies if e.alive]
        
        # Update bullets
        for bullet in self.bullets:
            bullet.update(dt)
        
        # Remove bullets that are off map
        self.bullets = [b for b in self.bullets 
                       if not b.is_off_map(self.width, self.height)]
        
        # Spawn new enemies periodically
        self._update_spawning(dt)
    
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
    
    def _update_spawning(self, dt):
        """Handle enemy spawning"""
        # Only spawn if under max limit
        if len(self.enemies) >= self.config.max_active_enemies:
            return
        
        self.spawn_timer += dt
        if self.spawn_timer >= self.config.spawn_interval:
            self.spawn_timer = 0
            self._spawn_enemy()
    
    def _spawn_enemy(self):
        """Spawn a new enemy using seed-based randomization"""
        # Use seed + counter for reproducible spawning
        if self.initial_seed is not None:
            random.seed(self.initial_seed + self.spawn_counter)
        
        self.spawn_counter += 1
        
        # Choose random position at edges
        edge = random.choice(['top', 'bottom', 'left', 'right'])
        
        if edge == 'top':
            x = random.uniform(5, self.width - 5)
            y = 5
        elif edge == 'bottom':
            x = random.uniform(5, self.width - 5)
            y = self.height - 5
        elif edge == 'left':
            x = 5
            y = random.uniform(5, self.height - 5)
        else:  # right
            x = self.width - 5
            y = random.uniform(5, self.height - 5)
        
        # Choose random enemy type
        enemy_type = random.choice(self.config.enemy_types)
        enemy = self._create_enemy(enemy_type, x, y)
        
        self.enemies.append(enemy)
    
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
LEVEL_1.spawn_interval = 8000  # 8 seconds between spawns
LEVEL_1.max_active_enemies = 10

LEVEL_2 = LevelConfig(
    width=120,
    height=70,
    seed=67890
)
LEVEL_2.min_enemies = 5
LEVEL_2.max_enemies = 10
LEVEL_2.enemy_fire_rate_multiplier = 1.2
LEVEL_2.spawn_interval = 5000  # 5 seconds between spawns
LEVEL_2.max_active_enemies = 15

