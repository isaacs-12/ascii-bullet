"""
Asteroids-style gameplay - using original game logic with green color scheme
"""

import pygame
import math
import random
from src.states.base_state import BaseState


# Game constants (from original)
player_size = 10
fd_fric = 0.5
bd_fric = 0.1
player_max_speed = 20
player_max_rtspd = 10
bullet_speed = 15
saucer_speed = 5
small_saucer_accuracy = 10

# Fixed playable area dimensions (pixels)
PLAYABLE_WIDTH = 800
PLAYABLE_HEIGHT = 600
BORDER_WIDTH = 2  # Border thickness in pixels


# Color scheme - green instead of white
green = (0, 255, 0)
black = (10, 10, 15)  # Terminal background color


def isColliding(x, y, xTo, yTo, size):
    """Check collision between two circular objects"""
    if x > xTo - size and x < xTo + size and y > yTo - size and y < yTo + size:
        return True
    return False


class Asteroid:
    """Asteroid class from original game"""
    def __init__(self, x, y, t):
        self.x = x
        self.y = y
        if t == "Large":
            self.size = 30
        elif t == "Normal":
            self.size = 20
        else:
            self.size = 10
        self.t = t

        # Make random speed and direction
        self.speed = random.uniform(1, (40 - self.size) * 4 / 15)
        self.dir = random.randrange(0, 360) * math.pi / 180

        # Make random asteroid sprites
        full_circle = random.uniform(18, 36)
        dist = random.uniform(self.size / 2, self.size)
        self.vertices = []
        while full_circle < 360:
            self.vertices.append([dist, full_circle])
            dist = random.uniform(self.size / 2, self.size)
            full_circle += random.uniform(18, 36)

    def updateAsteroid(self, gameDisplay, playable_width, playable_height, offset_x=0, offset_y=0):
        # Move asteroid (matching original physics exactly)
        self.x += self.speed * math.cos(self.dir)
        self.y += self.speed * math.sin(self.dir)

        # Check for wrapping (use fixed playable area)
        if self.x > playable_width:
            self.x = 0
        elif self.x < 0:
            self.x = playable_width
        elif self.y > playable_height:
            self.y = 0
        elif self.y < 0:
            self.y = playable_height

        # Draw asteroid (with border offset)
        for v in range(len(self.vertices)):
            if v == len(self.vertices) - 1:
                next_v = self.vertices[0]
            else:
                next_v = self.vertices[v + 1]
            this_v = self.vertices[v]
            pygame.draw.line(gameDisplay, green, 
                            (self.x + offset_x + this_v[0] * math.cos(this_v[1] * math.pi / 180),
                             self.y + offset_y + this_v[0] * math.sin(this_v[1] * math.pi / 180)),
                            (self.x + offset_x + next_v[0] * math.cos(next_v[1] * math.pi / 180),
                             self.y + offset_y + next_v[0] * math.sin(next_v[1] * math.pi / 180)))


class Bullet:
    """Bullet class from original game"""
    def __init__(self, x, y, direction):
        self.x = x
        self.y = y
        self.dir = direction
        self.life = 30

    def updateBullet(self, gameDisplay, playable_width, playable_height, offset_x, offset_y):
        # Moving
        self.x += bullet_speed * math.cos(self.dir * math.pi / 180)
        self.y += bullet_speed * math.sin(self.dir * math.pi / 180)

        # Drawing (with border offset) - only draw if within playable area
        draw_x = self.x + offset_x
        draw_y = self.y + offset_y
        if 0 <= draw_x < gameDisplay.get_width() and 0 <= draw_y < gameDisplay.get_height():
            pygame.draw.circle(gameDisplay, green, (int(draw_x), int(draw_y)), 3)

        # Wrapping (use fixed playable area)
        if self.x > playable_width:
            self.x = 0
        elif self.x < 0:
            self.x = playable_width
        elif self.y > playable_height:
            self.y = 0
        elif self.y < 0:
            self.y = playable_height
        self.life -= 1


class Saucer:
    """Saucer class from original game"""
    def __init__(self):
        self.x = 0
        self.y = 0
        self.state = "Dead"
        self.type = "Large"
        self.dirchoice = ()
        self.bullets = []
        self.cd = 0
        self.bdir = 0
        self.soundDelay = 0

    def updateSaucer(self, gameDisplay, player_x, player_y, stage, playable_width, playable_height):
        # Move saucer
        self.x += saucer_speed * math.cos(self.dir * math.pi / 180)
        self.y += saucer_speed * math.sin(self.dir * math.pi / 180)

        # Choose random direction
        if random.randrange(0, 100) == 1:
            self.dir = random.choice(self.dirchoice)

        # Wrapping (use fixed playable area)
        if self.y < 0:
            self.y = playable_height
        elif self.y > playable_height:
            self.y = 0
        if self.x < 0 or self.x > playable_width:
            self.state = "Dead"

        # Shooting
        if self.type == "Large":
            self.bdir = random.randint(0, 360)
        else:
            # Small saucer aims at player
            acc = small_saucer_accuracy * 4 / stage
            self.bdir = math.degrees(math.atan2(-self.y + player_y, -self.x + player_x) + 
                                    math.radians(random.uniform(acc, -acc)))
        if self.cd == 0:
            self.bullets.append(Bullet(self.x, self.y, self.bdir))
            self.cd = 30
        else:
            self.cd -= 1

    def createSaucer(self, display_width, display_height):
        # Create saucer
        self.state = "Alive"

        # Set random position
        self.x = random.choice((0, display_width))
        self.y = random.randint(0, display_height)

        # Set random type
        if random.randint(0, 1) == 0:
            self.type = "Large"
            self.size = 20
        else:
            self.type = "Small"
            self.size = 10

        # Create random direction
        if self.x == 0:
            self.dir = 0
            self.dirchoice = (0, 45, -45)
        else:
            self.dir = 180
            self.dirchoice = (180, 135, -135)

        # Reset bullet cooldown
        self.cd = 0

    def drawSaucer(self, gameDisplay, offset_x=0, offset_y=0):
        # Draw saucer (with border offset)
        pygame.draw.polygon(gameDisplay, green,
                            ((self.x + offset_x + self.size, self.y + offset_y),
                             (self.x + offset_x + self.size / 2, self.y + offset_y + self.size / 3),
                             (self.x + offset_x - self.size / 2, self.y + offset_y + self.size / 3),
                             (self.x + offset_x - self.size, self.y + offset_y),
                             (self.x + offset_x - self.size / 2, self.y + offset_y - self.size / 3),
                             (self.x + offset_x + self.size / 2, self.y + offset_y - self.size / 3)), 1)
        pygame.draw.line(gameDisplay, green,
                         (self.x + offset_x - self.size, self.y + offset_y),
                         (self.x + offset_x + self.size, self.y + offset_y))
        pygame.draw.polygon(gameDisplay, green,
                            ((self.x + offset_x - self.size / 2, self.y + offset_y - self.size / 3),
                             (self.x + offset_x - self.size / 3, self.y + offset_y - 2 * self.size / 3),
                             (self.x + offset_x + self.size / 3, self.y + offset_y - 2 * self.size / 3),
                             (self.x + offset_x + self.size / 2, self.y + offset_y - self.size / 3)), 1)


class deadPlayer:
    """Dead player fragments class from original game"""
    def __init__(self, x, y, l):
        self.angle = random.randrange(0, 360) * math.pi / 180
        self.dir = random.randrange(0, 360) * math.pi / 180
        self.rtspd = random.uniform(-0.25, 0.25)
        self.x = x
        self.y = y
        self.lenght = l
        self.speed = random.randint(2, 8)

    def updateDeadPlayer(self, gameDisplay, offset_x=0, offset_y=0):
        pygame.draw.line(gameDisplay, green,
                         (self.x + offset_x + self.lenght * math.cos(self.angle) / 2,
                          self.y + offset_y + self.lenght * math.sin(self.angle) / 2),
                         (self.x + offset_x - self.lenght * math.cos(self.angle) / 2,
                          self.y + offset_y - self.lenght * math.sin(self.angle) / 2))
        self.angle += self.rtspd
        self.x += self.speed * math.cos(self.dir)
        self.y += self.speed * math.sin(self.dir)


class Player:
    """Player class from original game"""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.hspeed = 0
        self.vspeed = 0
        self.dir = -90
        self.rtspd = 0
        self.thrust = False

    def updatePlayer(self, display_width, display_height):
        # Move player
        speed = math.sqrt(self.hspeed**2 + self.vspeed**2)
        if self.thrust:
            if speed + fd_fric < player_max_speed:
                self.hspeed += fd_fric * math.cos(self.dir * math.pi / 180)
                self.vspeed += fd_fric * math.sin(self.dir * math.pi / 180)
            else:
                self.hspeed = player_max_speed * math.cos(self.dir * math.pi / 180)
                self.vspeed = player_max_speed * math.sin(self.dir * math.pi / 180)
        else:
            if speed - bd_fric > 0:
                change_in_hspeed = (bd_fric * math.cos(math.atan2(self.vspeed, self.hspeed) if self.hspeed != 0 else 0))
                change_in_vspeed = (bd_fric * math.sin(math.atan2(self.vspeed, self.hspeed) if self.hspeed != 0 else 0))
                if self.hspeed != 0:
                    if change_in_hspeed / abs(change_in_hspeed) == self.hspeed / abs(self.hspeed):
                        self.hspeed -= change_in_hspeed
                    else:
                        self.hspeed += change_in_hspeed
                if self.vspeed != 0:
                    if change_in_vspeed / abs(change_in_vspeed) == self.vspeed / abs(self.vspeed):
                        self.vspeed -= change_in_vspeed
                    else:
                        self.vspeed += change_in_vspeed
            else:
                self.hspeed = 0
                self.vspeed = 0
        self.x += self.hspeed
        self.y += self.vspeed

        # Check for wrapping
        if self.x > display_width:
            self.x = 0
        elif self.x < 0:
            self.x = display_width
        elif self.y > display_height:
            self.y = 0
        elif self.y < 0:
            self.y = display_height

        # Rotate player
        self.dir += self.rtspd

    def drawPlayer(self, gameDisplay, offset_x=0, offset_y=0):
        a = math.radians(self.dir)
        x = self.x + offset_x
        y = self.y + offset_y
        s = player_size
        t = self.thrust
        # Draw player (with border offset)
        pygame.draw.line(gameDisplay, green,
                         (x - (s * math.sqrt(130) / 12) * math.cos(math.atan(7 / 9) + a),
                          y - (s * math.sqrt(130) / 12) * math.sin(math.atan(7 / 9) + a)),
                         (x + s * math.cos(a), y + s * math.sin(a)))

        pygame.draw.line(gameDisplay, green,
                         (x - (s * math.sqrt(130) / 12) * math.cos(math.atan(7 / 9) - a),
                          y + (s * math.sqrt(130) / 12) * math.sin(math.atan(7 / 9) - a)),
                         (x + s * math.cos(a), y + s * math.sin(a)))

        pygame.draw.line(gameDisplay, green,
                         (x - (s * math.sqrt(2) / 2) * math.cos(a + math.pi / 4),
                          y - (s * math.sqrt(2) / 2) * math.sin(a + math.pi / 4)),
                         (x - (s * math.sqrt(2) / 2) * math.cos(-a + math.pi / 4),
                          y + (s * math.sqrt(2) / 2) * math.sin(-a + math.pi / 4)))
        if t:
            pygame.draw.line(gameDisplay, green,
                             (x - s * math.cos(a),
                              y - s * math.sin(a)),
                             (x - (s * math.sqrt(5) / 4) * math.cos(a + math.pi / 6),
                              y - (s * math.sqrt(5) / 4) * math.sin(a + math.pi / 6)))
            pygame.draw.line(gameDisplay, green,
                             (x - s * math.cos(-a),
                              y + s * math.sin(-a)),
                             (x - (s * math.sqrt(5) / 4) * math.cos(-a + math.pi / 6),
                              y + (s * math.sqrt(5) / 4) * math.sin(-a + math.pi / 6)))

    def killPlayer(self, display_width, display_height):
        # Reset the player
        self.x = display_width / 2
        self.y = display_height / 2
        self.thrust = False
        self.dir = -90
        self.hspeed = 0
        self.vspeed = 0


def drawText(gameDisplay, msg, color, x, y, s, center=True):
    """Draw text function from original game"""
    font = pygame.font.Font(pygame.font.match_font('courier', bold=True), s)
    screen_text = font.render(msg, True, color)
    if center:
        rect = screen_text.get_rect()
        rect.center = (x, y)
    else:
        rect = (x, y)
    gameDisplay.blit(screen_text, rect)


class AsteroidsGameplayState(BaseState):
    """Asteroids gameplay state using original game logic"""
    
    def __init__(self, game, previous_state):
        super().__init__(game)
        self.previous_state = previous_state
        
        # Fixed playable area dimensions
        self.playable_width = PLAYABLE_WIDTH
        self.playable_height = PLAYABLE_HEIGHT
        
        # Calculate required window size (playable area + border + padding)
        required_width = self.playable_width + (BORDER_WIDTH * 2) + 40  # Extra padding for UI
        required_height = self.playable_height + (BORDER_WIDTH * 2) + 40
        
        # Get current screen size
        current_width = self.renderer.screen.get_width()
        current_height = self.renderer.screen.get_height()
        
        # Resize window if too small
        if current_width < required_width or current_height < required_height:
            new_width = max(required_width, current_width)
            new_height = max(required_height, current_height)
            # Resize the window and update renderer's screen reference
            self.renderer.screen = pygame.display.set_mode((new_width, new_height), pygame.RESIZABLE)
            pygame.display.set_caption("ASCII BULLET HELL - Asteroids")
        
        # Calculate playable area offset (centered in window, accounting for border)
        screen_width = self.renderer.screen.get_width()
        screen_height = self.renderer.screen.get_height()
        self.border_offset_x = (screen_width - self.playable_width) // 2
        self.border_offset_y = (screen_height - self.playable_height) // 2
        
        # Use fixed dimensions for game logic
        self.display_width = self.playable_width
        self.display_height = self.playable_height
        
        # Game state variables (from original gameLoop)
        self.gameState = "Playing"
        self.player_state = "Alive"
        self.player_blink = 0
        self.player_pieces = []
        self.player_dying_delay = 0
        self.player_invi_dur = 0
        self.hyperspace = 0
        self.next_level_delay = 0
        self.bullet_capacity = 4
        self.bullets = []
        self.asteroids = []
        self.stage = 3
        self.score = 0
        self.live = 2
        self.oneUp_multiplier = 1
        self.playOneUpSFX = 0
        self.intensity = 0
        
        # Create entities
        self.player = Player(self.display_width / 2, self.display_height / 2)
        self.saucer = Saucer()
        
        # Spawn initial asteroids
        for i in range(self.stage):
            xTo = self.display_width / 2
            yTo = self.display_height / 2
            while (abs(xTo - self.display_width / 2) < self.display_width / 4 and 
                   abs(yTo - self.display_height / 2) < self.display_height / 4):
                xTo = random.randrange(0, self.display_width)
                yTo = random.randrange(0, self.display_height)
            self.asteroids.append(Asteroid(xTo, yTo, "Large"))
        
        # Frame timing (original game runs at 30 FPS)
        self.frame_timer = 0
        self.target_fps = 30
        self.frame_time = 1000.0 / self.target_fps
        
        # Playtime tracking
        import time
        self.game_start_time = time.time()
        self.stats_recorded = False
    
    def handle_events(self, events):
        """Handle input events"""
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    # Return to terminal
                    self.game.change_state(self.previous_state, call_enter=False)
                elif event.key == pygame.K_UP:
                    self.player.thrust = True
                elif event.key == pygame.K_LEFT:
                    self.player.rtspd = -player_max_rtspd
                elif event.key == pygame.K_RIGHT:
                    self.player.rtspd = player_max_rtspd
                elif event.key == pygame.K_SPACE:
                    if (self.player_dying_delay == 0 and 
                        len(self.bullets) < self.bullet_capacity):
                        self.bullets.append(Bullet(self.player.x, self.player.y, self.player.dir))
                elif event.key == pygame.K_LSHIFT:
                    self.hyperspace = 30
                elif event.key == pygame.K_r and self.gameState == "Game Over":
                    # Restart game
                    self.__init__(self.game, self.previous_state)
            
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_UP:
                    self.player.thrust = False
                elif event.key == pygame.K_LEFT or event.key == pygame.K_RIGHT:
                    self.player.rtspd = 0
    
    def update(self, dt):
        """Update game logic - original game logic"""
        # Record stats when game ends
        if self.gameState == "Game Over" and not self.stats_recorded:
            import time
            playtime_seconds = time.time() - self.game_start_time
            self.game.save_system.record_asteroids_game(self.score, self.stage)
            self.game.save_system.add_playtime(playtime_seconds, "asteroids")
            self.stats_recorded = True
            return
        
        if self.gameState == "Game Over":
            return
        
        # Use fixed dimensions (don't update from screen)
        # self.display_width and self.display_height are already set to fixed values
        
        # Update player
        self.player.updatePlayer(self.display_width, self.display_height)
        
        # Checking player invincible time
        if self.player_invi_dur != 0:
            self.player_invi_dur -= 1
        elif self.hyperspace == 0:
            self.player_state = "Alive"
        
        # Hyperspace
        if self.hyperspace != 0:
            self.player_state = "Died"
            self.hyperspace -= 1
            if self.hyperspace == 1:
                self.player.x = random.randrange(0, self.display_width)
                self.player.y = random.randrange(0, self.display_height)
        
        # Check for collision w/ asteroid
        for a in self.asteroids[:]:
            if self.player_state != "Died":
                if isColliding(self.player.x, self.player.y, a.x, a.y, a.size):
                    # Create ship fragments
                    length = 5 * player_size / (2 * math.cos(math.atan(1 / 3)))
                    self.player_pieces.append(deadPlayer(self.player.x, self.player.y, length))
                    self.player_pieces.append(deadPlayer(self.player.x, self.player.y, length))
                    self.player_pieces.append(deadPlayer(self.player.x, self.player.y, player_size))
                    
                    # Kill player
                    self.player_state = "Died"
                    self.player_dying_delay = 30
                    self.player_invi_dur = 120
                    self.player.killPlayer(self.display_width, self.display_height)
                    
                    if self.live != 0:
                        self.live -= 1
                    else:
                        self.gameState = "Game Over"
                    
                    # Split asteroid
                    if a.t == "Large":
                        self.asteroids.append(Asteroid(a.x, a.y, "Normal"))
                        self.asteroids.append(Asteroid(a.x, a.y, "Normal"))
                        self.score += 20
                    elif a.t == "Normal":
                        self.asteroids.append(Asteroid(a.x, a.y, "Small"))
                        self.asteroids.append(Asteroid(a.x, a.y, "Small"))
                        self.score += 50
                    else:
                        self.score += 100
                    
                    self.asteroids.remove(a)
        
        # Update ship fragments
        for f in self.player_pieces[:]:
            if (f.x > self.display_width or f.x < 0 or 
                f.y > self.display_height or f.y < 0):
                self.player_pieces.remove(f)
        
        # Check for end of stage
        if len(self.asteroids) == 0 and self.saucer.state == "Dead":
            if self.next_level_delay < 30:
                self.next_level_delay += 1
            else:
                self.stage += 1
                self.intensity = 0
                # Spawn asteroid away of center
                for i in range(self.stage):
                    xTo = self.display_width / 2
                    yTo = self.display_height / 2
                    while (abs(xTo - self.display_width / 2) < self.display_width / 4 and 
                           abs(yTo - self.display_height / 2) < self.display_height / 4):
                        xTo = random.randrange(0, self.display_width)
                        yTo = random.randrange(0, self.display_height)
                    self.asteroids.append(Asteroid(xTo, yTo, "Large"))
                self.next_level_delay = 0
        
        # Update intensity
        if self.intensity < self.stage * 450:
            self.intensity += 1
        
        # Saucer
        if self.saucer.state == "Dead":
            if (random.randint(0, 6000) <= (self.intensity * 2) / (self.stage * 9) and 
                self.next_level_delay == 0):
                self.saucer.createSaucer(self.playable_width, self.playable_height)
                # Only small saucers >40000
                if self.score >= 40000:
                    self.saucer.type = "Small"
        else:
            # Set saucer target dir
            acc = small_saucer_accuracy * 4 / self.stage
            self.saucer.bdir = math.degrees(math.atan2(-self.saucer.y + self.player.y, 
                                                       -self.saucer.x + self.player.x) + 
                                            math.radians(random.uniform(acc, -acc)))
            
            # Check for collision w/ asteroid
            for a in self.asteroids[:]:
                if isColliding(self.saucer.x, self.saucer.y, a.x, a.y, a.size + self.saucer.size):
                    self.saucer.state = "Dead"
                    if a.t == "Large":
                        self.asteroids.append(Asteroid(a.x, a.y, "Normal"))
                        self.asteroids.append(Asteroid(a.x, a.y, "Normal"))
                    elif a.t == "Normal":
                        self.asteroids.append(Asteroid(a.x, a.y, "Small"))
                        self.asteroids.append(Asteroid(a.x, a.y, "Small"))
                    self.asteroids.remove(a)
            
            # Check for collision w/ bullet
            for b in self.bullets[:]:
                if isColliding(b.x, b.y, self.saucer.x, self.saucer.y, self.saucer.size):
                    if self.saucer.type == "Large":
                        self.score += 200
                    else:
                        self.score += 1000
                    self.saucer.state = "Dead"
                    self.bullets.remove(b)
            
            # Check collision w/ player
            if isColliding(self.saucer.x, self.saucer.y, self.player.x, self.player.y, self.saucer.size):
                if self.player_state != "Died":
                    length = 5 * player_size / (2 * math.cos(math.atan(1 / 3)))
                    self.player_pieces.append(deadPlayer(self.player.x, self.player.y, length))
                    self.player_pieces.append(deadPlayer(self.player.x, self.player.y, length))
                    self.player_pieces.append(deadPlayer(self.player.x, self.player.y, player_size))
                    self.player_state = "Died"
                    self.player_dying_delay = 30
                    self.player_invi_dur = 120
                    self.player.killPlayer(self.display_width, self.display_height)
                    if self.live != 0:
                        self.live -= 1
                    else:
                        self.gameState = "Game Over"
            
            # Saucer's bullets
            for b in self.saucer.bullets[:]:
                # Check for collision w/ asteroids
                for a in self.asteroids[:]:
                    if isColliding(b.x, b.y, a.x, a.y, a.size):
                        if a.t == "Large":
                            self.asteroids.append(Asteroid(a.x, a.y, "Normal"))
                            self.asteroids.append(Asteroid(a.x, a.y, "Normal"))
                        elif a.t == "Normal":
                            self.asteroids.append(Asteroid(a.x, a.y, "Small"))
                            self.asteroids.append(Asteroid(a.x, a.y, "Small"))
                        self.asteroids.remove(a)
                        self.saucer.bullets.remove(b)
                        break
                
                # Check for collision w/ player
                if isColliding(self.player.x, self.player.y, b.x, b.y, 5):
                    if self.player_state != "Died":
                        length = 5 * player_size / (2 * math.cos(math.atan(1 / 3)))
                        self.player_pieces.append(deadPlayer(self.player.x, self.player.y, length))
                        self.player_pieces.append(deadPlayer(self.player.x, self.player.y, length))
                        self.player_pieces.append(deadPlayer(self.player.x, self.player.y, player_size))
                        self.player_state = "Died"
                        self.player_dying_delay = 30
                        self.player_invi_dur = 120
                        self.player.killPlayer(self.display_width, self.display_height)
                        if self.live != 0:
                            self.live -= 1
                        else:
                            self.gameState = "Game Over"
                        self.saucer.bullets.remove(b)
                
                if b.life <= 0:
                    if b in self.saucer.bullets:
                        self.saucer.bullets.remove(b)
        
        # Bullets
        for b in self.bullets[:]:
            # Check for bullets collide w/ asteroid
            for a in self.asteroids[:]:
                if (b.x > a.x - a.size and b.x < a.x + a.size and 
                    b.y > a.y - a.size and b.y < a.y + a.size):
                    if a.t == "Large":
                        self.asteroids.append(Asteroid(a.x, a.y, "Normal"))
                        self.asteroids.append(Asteroid(a.x, a.y, "Normal"))
                        self.score += 20
                    elif a.t == "Normal":
                        self.asteroids.append(Asteroid(a.x, a.y, "Small"))
                        self.asteroids.append(Asteroid(a.x, a.y, "Small"))
                        self.score += 50
                    else:
                        self.score += 100
                    self.asteroids.remove(a)
                    self.bullets.remove(b)
                    break
            
            if b.life <= 0:
                if b in self.bullets:
                    self.bullets.remove(b)
        
        # Extra live
        if self.score > self.oneUp_multiplier * 10000:
            self.oneUp_multiplier += 1
            self.live += 1
    
    def render(self):
        """Render the game - original rendering logic"""
        # If game over, only show terminal renderer game over screen
        if self.gameState == "Game Over":
            self.renderer.clear()
            color = self.renderer.COLORS['fg']
            
            center_y = self.renderer.char_height // 2
            
            # Game over message
            self.renderer.write_centered(center_y - 3, "GAME OVER", (255, 0, 0))
            self.renderer.write_centered(center_y - 1, f"Final Score: {self.score}", color)
            self.renderer.write_centered(center_y + 1, f"Stage Reached: {self.stage}", color)
            
            # Check if it's a new best score
            best_score = self.game.save_system.get_stat("asteroids_best_score")
            if self.score >= best_score and self.score > 0:
                self.renderer.write_centered(center_y + 3, "NEW HIGH SCORE!", (0, 255, 0))
            
            self.renderer.write_centered(center_y + 5, "Press R to restart or ESC to quit", (150, 150, 150))
            
            # Render terminal overlay
            self.renderer.render()
            return  # Early return - don't render game entities
        
        # Normal gameplay rendering
        # Use the renderer's screen directly
        gameDisplay = self.renderer.screen
        
        # Recalculate border offsets in case window was resized
        screen_width = gameDisplay.get_width()
        screen_height = gameDisplay.get_height()
        self.border_offset_x = (screen_width - self.playable_width) // 2
        self.border_offset_y = (screen_height - self.playable_height) // 2
        
        # Reset display
        gameDisplay.fill(black)
        
        # Draw ASCII border around playable area
        self._draw_border(gameDisplay)

        # Set clipping rectangle to playable area (so entities don't overlap borders)
        playable_rect = pygame.Rect(
            self.border_offset_x,
            self.border_offset_y,
            self.playable_width,
            self.playable_height
        )
        old_clip = gameDisplay.get_clip()
        gameDisplay.set_clip(playable_rect)

        
        
        # Update and draw asteroids (using fixed dimensions)
        for a in self.asteroids:
            a.updateAsteroid(gameDisplay, self.playable_width, self.playable_height,
                           self.border_offset_x, self.border_offset_y)
        
        # Update and draw saucer
        if self.saucer.state == "Alive":
            self.saucer.updateSaucer(gameDisplay, self.player.x, self.player.y, self.stage,
                                    self.playable_width, self.playable_height)
            self.saucer.drawSaucer(gameDisplay, self.border_offset_x, self.border_offset_y)
        
        # Update and draw saucer bullets
        for b in self.saucer.bullets[:]:
            b.updateBullet(gameDisplay, self.playable_width, self.playable_height,
                          self.border_offset_x, self.border_offset_y)
            if b.life <= 0:
                if b in self.saucer.bullets:
                    self.saucer.bullets.remove(b)
        
        # Update and draw bullets
        for b in self.bullets[:]:
            b.updateBullet(gameDisplay, self.playable_width, self.playable_height,
                          self.border_offset_x, self.border_offset_y)
            if b.life <= 0:
                if b in self.bullets:
                    self.bullets.remove(b)
        
        # Update and draw ship fragments
        for f in self.player_pieces[:]:
            f.updateDeadPlayer(gameDisplay, self.border_offset_x, self.border_offset_y)
            if (f.x > self.display_width or f.x < 0 or 
                f.y > self.display_height or f.y < 0):
                self.player_pieces.remove(f)
        
        # Draw player
        if self.player_state == "Died":
            if self.hyperspace == 0:
                if self.player_dying_delay == 0:
                    if self.player_blink < 5:
                        if self.player_blink == 0:
                            self.player_blink = 10
                        else:
                            self.player.drawPlayer(gameDisplay, self.border_offset_x, self.border_offset_y)
                    self.player_blink -= 1
                else:
                    self.player_dying_delay -= 1
        else:
            self.player.drawPlayer(gameDisplay, self.border_offset_x, self.border_offset_y)
        
        # Draw score (with border offset)
        drawText(gameDisplay, str(self.score), green, 

                self.border_offset_x + 60, self.border_offset_y + 20, 40, False)
        
        # Draw Lives (with border offset)
        for l in range(self.live + 1):
            temp_player = Player(75 + l * 25, 75)
            temp_player.drawPlayer(gameDisplay, self.border_offset_x, self.border_offset_y)
        
        # Restore clipping rectangle
        gameDisplay.set_clip(old_clip)
        
        # Update screen

        gameDisplay.set_clip(old_clip)

        pygame.display.flip()
    
    def _draw_border(self, gameDisplay):
        """Draw ASCII border around the playable area"""
        border_color = green
        
        # Calculate border rectangle positions
        border_left = self.border_offset_x - BORDER_WIDTH
        border_right = self.border_offset_x + self.playable_width + BORDER_WIDTH
        border_top = self.border_offset_y - BORDER_WIDTH
        border_bottom = self.border_offset_y + self.playable_height + BORDER_WIDTH
        
        # Draw border using pygame rectangles (simpler and faster)
        # Top border
        pygame.draw.rect(gameDisplay, border_color, 
                        (border_left, border_top, border_right - border_left, BORDER_WIDTH))
        # Bottom border
        pygame.draw.rect(gameDisplay, border_color,
                        (border_left, border_bottom - BORDER_WIDTH, border_right - border_left, BORDER_WIDTH))
        # Left border
        pygame.draw.rect(gameDisplay, border_color,
                        (border_left, border_top, BORDER_WIDTH, border_bottom - border_top))
        # Right border
        pygame.draw.rect(gameDisplay, border_color,
                        (border_right - BORDER_WIDTH, border_top, BORDER_WIDTH, border_bottom - border_top))