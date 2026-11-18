"""
Galaga/Asteroids style ASCII shooter gameplay
"""

import math
import random

import pygame

from src.states.base_state import BaseState


class Entity:
    """Base class for game entities with fractional positioning"""

    def __init__(self, x, y, art):
        """
        Initialize entity

        Args:
            x: X position (fractional character width)
            y: Y position (fractional character height)
            art: List of strings representing the ASCII art
        """
        self.x = x
        self.y = y
        self.art = art
        self.width = max(len(line) for line in art) if art else 0
        self.height = len(art)
        self.alive = True
        self.velocity_x = 0.0
        self.velocity_y = 0.0

    def update(self, dt):
        """Update entity position based on velocity"""
        self.x += self.velocity_x * dt
        self.y += self.velocity_y * dt

    def get_render_pos(self):
        """Get integer position for rendering"""
        return (int(self.x), int(self.y))

    def collides_with(self, other):
        """Simple bounding box collision"""
        x1, y1 = self.get_render_pos()
        x2, y2 = other.get_render_pos()

        return (x1 < x2 + other.width and
                x1 + self.width > x2 and
                y1 < y2 + other.height and
                y1 + self.height > y2)


class PlayerShip(Entity):
    """The player's fighter ship"""

    def __init__(self, x, y):
        art = [
            "      ^      ",
            "     / \\     ",
            "    /   \\    ",
            "   |=[O]=|   ",
            "  /_/   \\_\\  "
        ]
        super().__init__(x, y, art)
        self.max_speed = 22.5  # Characters per second (increased 50%)

    def collides_with(self, other):
        """Custom collision - small hitbox around cockpit"""
        # Ship layout (13 chars wide, 5 rows tall):
        #   "      ^      " row 0
        #   "     / \     " row 1
        #   "    /   \    " row 2
        #   "   |=[O]=|   " row 3 - O is at index 6
        #   "  /_/   \_\  " row 4

        # Small rectangular hitbox: cockpit area covering =[O]= (indices 4-8, rows 2-3)
        cockpit_start_x = int(self.x) + 4
        cockpit_end_x = int(self.x) + 9  # Exclusive (covers indices 4, 5, 6, 7, 8)
        cockpit_start_y = int(self.y) + 2
        cockpit_end_y = int(self.y) + 4  # Exclusive (covers rows 2 and 3)

        # Get bullet's rendered position
        bullet_x = int(other.x)
        bullet_y = int(other.y)

        # Hit if bullet is in the cockpit area
        return (cockpit_start_x <= bullet_x < cockpit_end_x and
                cockpit_start_y <= bullet_y < cockpit_end_y)

    def _point_in_triangle(self, px, py, x1, y1, x2, y2, x3, y3):
        """Check if point (px, py) is inside triangle defined by (x1,y1), (x2,y2), (x3,y3)"""
        # Using barycentric coordinates
        denom = ((y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3))
        if abs(denom) < 0.001:  # Degenerate triangle
            return False

        a = ((y2 - y3) * (px - x3) + (x3 - x2) * (py - y3)) / denom
        b = ((y3 - y1) * (px - x3) + (x1 - x3) * (py - y3)) / denom
        c = 1 - a - b

        return 0 <= a <= 1 and 0 <= b <= 1 and 0 <= c <= 1


class Bullet(Entity):
    """Player bullet"""

    def __init__(self, x, y):
        art = ["|"]
        super().__init__(x, y, art)
        self.velocity_y = -30.0  # Move upward quickly


class EnemyBullet(Entity):
    """Enemy bullet"""

    def __init__(self, x, y):
        art = ["v"]
        super().__init__(x, y, art)
        self.velocity_y = 20.0  # Move downward


class Drone(Entity):
    """Small simple enemy"""

    def __init__(self, x, y):
        art = [
            "    _o_    ",
            "   /_^_\\   ",
            "   v   v   "
        ]
        super().__init__(x, y, art)
        self.shoot_cooldown = 0
        self.shoot_interval = random.uniform(3.0, 6.0)

        # Movement pattern
        self.formation_x = x
        self.formation_y = y
        self.dive_cooldown = random.uniform(3.0, 8.0)


class Guard(Entity):
    """Medium enemy"""

    def __init__(self, x, y):
        art = [
            "   _v_v_   ",
            "  /     \\  ",
            "  |>-0-<|  ",
            "  m     m  "
        ]
        super().__init__(x, y, art)
        self.shoot_cooldown = 0
        self.shoot_interval = random.uniform(4.0, 7.0)

        # Movement pattern
        self.formation_x = x
        self.formation_y = y
        self.dive_cooldown = random.uniform(4.0, 10.0)


class Boss(Entity):
    """Large boss enemy"""

    def __init__(self, x, y):
        art = [
            "    _,-^-,_    ",
            "   /_ \\_/ _\\   ",
            "  <=========^> ",
            "   /  | |  \\   ",
            "   v  v v  v   "
        ]
        super().__init__(x, y, art)
        self.shoot_cooldown = 0
        self.shoot_interval = random.uniform(2.0, 4.0)
        self.health = 5  # Boss takes multiple hits

        # Movement pattern
        self.formation_x = x
        self.formation_y = y
        self.dive_cooldown = random.uniform(5.0, 12.0)


class GalagaGameplayState(BaseState):
    """Galaga-style shooter gameplay"""

    def __init__(self, game, previous_state):
        super().__init__(game)
        self.previous_state = previous_state

        # Game entities
        self.player = PlayerShip(35, 40)
        self.enemies = []
        self.bullets = []
        self.enemy_bullets = []

        # Game state
        self.score = 0
        self.wave = 1
        self.game_over = False
        self.victory = False

        # Input state
        self.keys_held = set()

        # Shooting cooldown
        self.shoot_cooldown = 0
        self.shoot_delay = 0.3  # Seconds between shots

        # Synchronized movement patterns per enemy type
        self.drone_pattern_time = 0
        self.guard_pattern_time = 0
        self.boss_pattern_time = 0

        # Spawn first wave
        self._spawn_wave()

    def _spawn_wave(self):
        """Spawn a wave of enemies"""
        self.enemies = []

        # Calculate how many enemies based on wave
        num_drones = min(3 + self.wave, 8)
        num_guards = min(1 + self.wave // 2, 4)
        num_bosses = 1 if self.wave >= 3 else 0

        # Spawn drones in formation
        for i in range(num_drones):
            x = 10 + (i % 4) * 15
            y = 5 + (i // 4) * 6
            self.enemies.append(Drone(x, y))

        # Spawn guards
        for i in range(num_guards):
            x = 15 + i * 20
            y = 15
            self.enemies.append(Guard(x, y))

        # Spawn boss
        if num_bosses > 0:
            self.enemies.append(Boss(30, 3))

    def enter(self):
        """Called when entering this state"""
        pass

    def exit(self):
        """Called when exiting this state"""
        pass

    def handle_events(self, events):
        """Handle input events"""
        for event in events:
            if event.type == pygame.KEYDOWN:
                self.keys_held.add(event.key)

                if event.key == pygame.K_ESCAPE:
                    # Return to terminal
                    self.game.change_state(self.previous_state, call_enter=False)
                elif event.key == pygame.K_SPACE and not self.game_over:
                    # Shoot
                    if self.shoot_cooldown <= 0:
                        self._player_shoot()
                        self.shoot_cooldown = self.shoot_delay

            elif event.type == pygame.KEYUP:
                self.keys_held.discard(event.key)

    def _player_shoot(self):
        """Player fires a bullet"""
        # Spawn bullet from center of player
        bullet_x = self.player.x + self.player.width // 2
        bullet_y = self.player.y - 1
        self.bullets.append(Bullet(bullet_x, bullet_y))

    def update(self, dt):
        """Update game logic"""
        if self.game_over or self.victory:
            return

        dt_seconds = dt / 1000.0

        # Update shoot cooldown
        self.shoot_cooldown = max(0, self.shoot_cooldown - dt_seconds)

        # Player movement
        if pygame.K_LEFT in self.keys_held or pygame.K_a in self.keys_held:
            self.player.velocity_x = -self.player.max_speed
        elif pygame.K_RIGHT in self.keys_held or pygame.K_d in self.keys_held:
            self.player.velocity_x = self.player.max_speed
        else:
            self.player.velocity_x = 0

        # Update player
        self.player.update(dt_seconds)

        # Keep player in bounds
        self.player.x = max(0, min(self.player.x, 80 - self.player.width))

        # Update bullets
        for bullet in self.bullets[:]:
            bullet.update(dt_seconds)
            if bullet.y < 0:
                self.bullets.remove(bullet)

        # Update enemy bullets
        for bullet in self.enemy_bullets[:]:
            bullet.update(dt_seconds)
            if bullet.y > 50:
                self.enemy_bullets.remove(bullet)

        # Update synchronized pattern times for each enemy class
        self.drone_pattern_time += dt_seconds
        self.guard_pattern_time += dt_seconds
        self.boss_pattern_time += dt_seconds

        # Update enemies and make them shoot
        for enemy in self.enemies:
            # Get the synchronized pattern time for this enemy's class
            if isinstance(enemy, Boss):
                pattern_time = self.boss_pattern_time
            elif isinstance(enemy, Guard):
                pattern_time = self.guard_pattern_time
            else:  # Drone
                pattern_time = self.drone_pattern_time

            enemy.dive_cooldown -= dt_seconds

            # Galaga-style movement patterns
            if enemy.dive_cooldown <= 0:
                # Dive attack pattern
                enemy.dive_cooldown = random.uniform(8.0, 15.0)
                dive_amplitude = 20
                dive_speed = 3.0

                # Swooping pattern
                offset_x = dive_amplitude * math.sin(pattern_time * dive_speed)
                offset_y = 10 * math.sin(pattern_time * dive_speed * 0.5)

                target_x = enemy.formation_x + offset_x
                target_y = enemy.formation_y + offset_y

                # Move towards target
                dx = target_x - enemy.x
                dy = target_y - enemy.y
                dist = math.sqrt(dx * dx + dy * dy)

                if dist > 0.5:
                    enemy.velocity_x = (dx / dist) * 15
                    enemy.velocity_y = (dy / dist) * 8
                else:
                    enemy.velocity_x = 0
                    enemy.velocity_y = 0
            else:
                # Formation hovering - gentle side-to-side (synchronized by class)
                hover_offset = math.sin(pattern_time * 2.0) * 8
                target_x = enemy.formation_x + hover_offset

                dx = target_x - enemy.x
                enemy.velocity_x = dx * 2.0  # Smooth following
                enemy.velocity_y = (enemy.formation_y - enemy.y) * 1.0

            # Check for collisions with other enemies and push away
            for other in self.enemies:
                if other is enemy:
                    continue

                dx = enemy.x - other.x
                dy = enemy.y - other.y
                dist = math.sqrt(dx * dx + dy * dy)

                # If too close, push away
                min_dist = max(enemy.width, enemy.height) * 0.8
                if dist < min_dist and dist > 0:
                    push_force = (min_dist - dist) * 0.5
                    enemy.velocity_x += (dx / dist) * push_force
                    enemy.velocity_y += (dy / dist) * push_force

            enemy.update(dt_seconds)

            # Keep enemies in bounds
            enemy.x = max(0, min(enemy.x, 80 - enemy.width))
            enemy.y = max(-5, min(enemy.y, 50))

            # Enemy shooting
            enemy.shoot_cooldown -= dt_seconds
            if enemy.shoot_cooldown <= 0:
                enemy.shoot_cooldown = enemy.shoot_interval
                # Shoot from center of enemy
                bullet_x = enemy.x + enemy.width // 2
                bullet_y = enemy.y + enemy.height
                self.enemy_bullets.append(EnemyBullet(bullet_x, bullet_y))

        # Check bullet collisions with enemies
        for bullet in self.bullets[:]:
            for enemy in self.enemies[:]:
                if bullet.collides_with(enemy):
                    # Hit!
                    if isinstance(enemy, Boss):
                        enemy.health -= 1
                        if enemy.health <= 0:
                            self.enemies.remove(enemy)
                            self.score += 500
                    else:
                        self.enemies.remove(enemy)
                        if isinstance(enemy, Drone):
                            self.score += 100
                        elif isinstance(enemy, Guard):
                            self.score += 200

                    if bullet in self.bullets:
                        self.bullets.remove(bullet)
                    break

        # Check enemy bullet collisions with player
        for bullet in self.enemy_bullets[:]:
            if self.player.collides_with(bullet):
                self.game_over = True
                return

        # Check if wave is cleared
        if len(self.enemies) == 0:
            self.wave += 1
            if self.wave > 5:
                self.victory = True
            else:
                self._spawn_wave()

    def render(self):
        """Render the game"""
        self.renderer.clear()

        # Draw player
        if not self.game_over:
            self._draw_entity(self.player, (0, 255, 255))

        # Draw enemies
        for enemy in self.enemies:
            if isinstance(enemy, Boss):
                self._draw_entity(enemy, (255, 0, 255))
            elif isinstance(enemy, Guard):
                self._draw_entity(enemy, (255, 255, 0))
            else:
                self._draw_entity(enemy, (255, 100, 100))

        # Draw bullets
        for bullet in self.bullets:
            self._draw_entity(bullet, (0, 255, 0))

        for bullet in self.enemy_bullets:
            self._draw_entity(bullet, (255, 0, 0))

        # Draw HUD
        self.renderer.write(2, 1, f"WAVE: {self.wave}  SCORE: {self.score}", (255, 255, 255))

        # Game over / victory messages
        if self.game_over:
            self.renderer.write_centered(20, "GAME OVER", (255, 0, 0))
            self.renderer.write_centered(22, f"Final Score: {self.score}", (255, 255, 255))
            self.renderer.write_centered(24, "Press ESC to return to terminal", (150, 150, 150))
        elif self.victory:
            self.renderer.write_centered(20, "VICTORY!", (0, 255, 0))
            self.renderer.write_centered(22, f"Final Score: {self.score}", (255, 255, 255))
            self.renderer.write_centered(24, "Press ESC to return to terminal", (150, 150, 150))

        self.renderer.render()

    def _draw_entity(self, entity, color):
        """Draw an entity at its position"""
        x, y = entity.get_render_pos()

        for i, line in enumerate(entity.art):
            if 0 <= y + i < self.renderer.char_height:
                # Trim line if it goes off screen
                max_x = min(len(line), self.renderer.char_width - x)
                if max_x > 0:
                    self.renderer.write(x, y + i, line[:max_x], color)

