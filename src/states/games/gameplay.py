"""Gameplay state"""

import pygame
from src.states.base_state import BaseState
from src.core.entities import Player
from src.core.camera import Camera
from src.core.level import Level, LEVEL_1


class GameplayState(BaseState):
    """Active gameplay state"""
    
    def __init__(self, game, previous_state=None, level_config=None):
        super().__init__(game)
        
        # Store previous state to return to
        self.previous_state = previous_state
        
        # Use default level if none provided
        if level_config is None:
            level_config = LEVEL_1
        
        # Create level
        self.level = Level(level_config)
        
        # Create player (start in bottom-left area)
        self.player = Player(
            self.level.width * 0.1,
            self.level.height * 0.5
        )
        
        # Create camera
        self.camera = Camera(
            viewport_width=self.renderer.char_width,
            viewport_height=self.renderer.char_height,
            map_width=self.level.width,
            map_height=self.level.height
        )
        
        # Game state
        self.paused = False
        self.game_over = False
        self.survival_time = 0
        self.score = 0
        
        # Proximity scoring tracking (to avoid double-counting)
        self.bullet_proximity_tracked = {}  # bullet_id -> last_scored_distance
    
    def handle_events(self, events):
        """Handle input events"""
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    # Return to previous menu state without calling enter() to preserve state
                    if self.previous_state:
                        self.game.change_state(self.previous_state, call_enter=False)
                    else:
                        # Fallback: create new menu if no previous state
                        from src.states.main_menu import MainMenuState
                        self.game.change_state(MainMenuState(self.game))
                    return
                
                # Check for Ctrl+C
                if event.key == pygame.K_c and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    # Return to previous menu state without calling enter() to preserve state
                    if self.previous_state:
                        self.game.change_state(self.previous_state, call_enter=False)
                    else:
                        # Fallback: create new menu if no previous state
                        from src.states.main_menu import MainMenuState
                        self.game.change_state(MainMenuState(self.game))
                    return
    
    def update(self, dt):
        """Update game logic"""
        if self.paused or self.game_over:
            return
        
        # Track survival time
        self.survival_time += dt
        
        # Handle player movement
        keys = pygame.key.get_pressed()
        dx = 0
        dy = 0
        
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dx -= 1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx += 1
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            dy -= 1
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            dy += 1
        
        # Move player
        if dx != 0 or dy != 0:
            self.player.move(dx, dy, dt, self.level.width, self.level.height)
        
        # Update camera to follow player (use cell coordinates)
        player_cell_x, player_cell_y = self.player.get_cell_position()
        self.camera.update(player_cell_x, player_cell_y)
        
        # Update level (enemies and bullets)
        self.level.update(dt, self.player)
        
        # Calculate proximity scoring
        self._calculate_proximity_score()
        
        # Check collisions
        if self.level.check_collisions(self.player):
            self.game_over = True
            # Save score on game over
            self.game.save_system.add_score(self.score, self.survival_time)
            # Track playtime
            playtime_seconds = self.survival_time / 1000.0
            self.game.save_system.add_playtime(playtime_seconds, "bullet_hell")
    
    def render(self):
        """Render the game"""
        self.renderer.clear()
        
        # Draw map boundaries (if visible)
        self._draw_map_boundaries()
        
        # Draw entities (use fractional cell coordinates for smooth rendering)
        for entity in self.level.get_entities():
            ex, ey = entity.get_cell_position()
            screen_pos = self.camera.world_to_screen(ex, ey)
            if screen_pos:
                sx, sy = screen_pos
                self.renderer.write(sx, sy, entity.char, entity.color)
        
        # Draw player (use fractional cell coordinates for smooth rendering)
        player_cell_x, player_cell_y = self.player.get_cell_position()
        screen_pos = self.camera.world_to_screen(player_cell_x, player_cell_y)
        if screen_pos:
            sx, sy = screen_pos
            self.renderer.write(sx, sy, self.player.char, self.player.color)
        
        # Draw HUD
        self._draw_hud()
        
        # Draw game over message
        if self.game_over:
            self._draw_game_over()
        
        self.renderer.render()
    
    def _draw_map_boundaries(self):
        """Draw visual indicators of map boundaries"""
        min_x, min_y, max_x, max_y = self.camera.get_visible_bounds()
        
        # Draw top boundary
        if min_y == 0:
            for x in range(max(0, min_x), min(self.level.width, max_x)):
                screen_pos = self.camera.world_to_screen(x, 0)
                if screen_pos:
                    sx, sy = screen_pos
                    self.renderer.write(sx, sy, '#', self.renderer.COLORS['menu_normal'])
        
        # Draw bottom boundary
        if max_y >= self.level.height:
            for x in range(max(0, min_x), min(self.level.width, max_x)):
                screen_pos = self.camera.world_to_screen(x, self.level.height - 1)
                if screen_pos:
                    sx, sy = screen_pos
                    self.renderer.write(sx, sy, '#', self.renderer.COLORS['menu_normal'])
        
        # Draw left boundary
        if min_x == 0:
            for y in range(max(0, min_y), min(self.level.height, max_y)):
                screen_pos = self.camera.world_to_screen(0, y)
                if screen_pos:
                    sx, sy = screen_pos
                    self.renderer.write(sx, sy, '#', self.renderer.COLORS['menu_normal'])
        
        # Draw right boundary
        if max_x >= self.level.width:
            for y in range(max(0, min_y), min(self.level.height, max_y)):
                screen_pos = self.camera.world_to_screen(self.level.width - 1, y)
                if screen_pos:
                    sx, sy = screen_pos
                    self.renderer.write(sx, sy, '#', self.renderer.COLORS['menu_normal'])
    
    def _calculate_proximity_score(self):
        """Calculate score based on proximity to bullets"""
        # Scoring tiers: distance -> points
        scoring_tiers = [
            (1.0, 50),   # Within 1 tile = 50 points
            (2.0, 25),   # Within 2 tiles = 25 points
            (3.0, 10),   # Within 3 tiles = 10 points
            (4.0, 5),    # Within 4 tiles = 5 points
        ]
        
        for bullet in self.level.bullets:
            bullet_id = id(bullet)
            
            # Calculate distance to player (use cell coordinates)
            px, py = self.player.get_cell_position()
            bx, by = bullet.get_cell_position()
            dx = px - bx
            dy = py - by
            distance = (dx**2 + dy**2) ** 0.5
            
            # Check each tier from closest to farthest
            for tier_distance, points in scoring_tiers:
                if distance <= tier_distance:
                    # Only award points if we haven't scored this tier for this bullet yet
                    last_scored = self.bullet_proximity_tracked.get(bullet_id, 999)
                    if tier_distance < last_scored:
                        self.score += points
                        self.bullet_proximity_tracked[bullet_id] = tier_distance
                    break
        
        # Clean up tracking for bullets that no longer exist
        current_bullet_ids = {id(b) for b in self.level.bullets}
        self.bullet_proximity_tracked = {
            bid: dist for bid, dist in self.bullet_proximity_tracked.items()
            if bid in current_bullet_ids
        }
    
    def _draw_hud(self):
        """Draw heads-up display"""
        # Score
        score_text = f"Score: {self.score}"
        self.renderer.write(1, 0, score_text, self.renderer.COLORS['menu_selected'])
        
        # Time survived
        seconds = int(self.survival_time / 1000)
        time_text = f"Time: {seconds}s"
        self.renderer.write(1, 1, time_text, self.renderer.COLORS['fg'])
        
        # Enemy count
        enemy_count = len(self.level.enemies)
        bullet_count = len(self.level.bullets)
        stats_text = f"Enemies: {enemy_count}  Bullets: {bullet_count}"
        self.renderer.write(1, 2, stats_text, self.renderer.COLORS['fg'])
        
        # Controls hint
        hint = "ESC: Menu"
        self.renderer.write(
            self.renderer.char_width - len(hint) - 1, 
            0, 
            hint, 
            self.renderer.COLORS['menu_normal']
        )
    
    def _draw_game_over(self):
        """Draw game over screen"""
        messages = [
            "GAME OVER",
            "",
            f"Final Score: {self.score}",
            f"Time Survived: {int(self.survival_time / 1000)} seconds",
            ""
        ]
        
        # Check if it's a high score
        if self.game.save_system.is_high_score(self.score):
            messages.append("NEW HIGH SCORE!")
            messages.append("")
        
        messages.append("Press ESC to return to menu")
        
        start_y = (self.renderer.char_height - len(messages)) // 2
        
        for i, message in enumerate(messages):
            self.renderer.write_centered(start_y + i, message, self.renderer.COLORS['menu_selected'])

