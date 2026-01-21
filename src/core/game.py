"""Main game class"""

import sys
import time
import pygame
from src.core.terminal_renderer import TerminalRenderer
from src.states.main_menu import MainMenuState
from src.core.save_system import SaveSystem


class Game:
    """Main game controller"""
    
    def __init__(self):
        """Initialize the game"""
        # Initialize save system
        self.save_system = SaveSystem()
        
        # Create terminal renderer
        self.renderer = TerminalRenderer(width=160, height=75, cell_size=14)
        
        # Game state
        self.running = True
        self.current_state = None
        
        # Playtime tracking
        self.session_start_time = time.time()
        self.last_playtime_save = time.time()
        self.playtime_save_interval = 30.0  # Save playtime every 30 seconds
        
        # Initialize with main menu
        self.change_state(MainMenuState(self))
    
    def change_state(self, new_state, call_enter=True):
        """
        Change to a new game state
        
        Args:
            new_state: The new state to switch to
            call_enter: Whether to call enter() on the new state (default True)
        """
        if self.current_state:
            self.current_state.exit()
        
        self.current_state = new_state
        if call_enter:
            self.current_state.enter()
    
    def handle_events(self):
        """Handle pygame events"""
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.VIDEORESIZE:
                # Handle window resize
                self.renderer.handle_resize(event.w, event.h)
        
        # Pass events to current state
        if self.current_state:
            self.current_state.handle_events(events)
    
    def update(self, dt):
        """
        Update game logic
        
        Args:
            dt: Delta time in milliseconds
        """
        if self.current_state:
            self.current_state.update(dt)
        
        # Track playtime
        current_time = time.time()
        elapsed = current_time - self.last_playtime_save
        
        if elapsed >= self.playtime_save_interval:
            # Save playtime periodically
            dt_seconds = elapsed
            self.save_system.add_playtime(dt_seconds, "total")
            self.last_playtime_save = current_time
    
    def render(self):
        """Render the current game state"""
        if self.current_state:
            self.current_state.render()
    
    def run(self):
        """Main game loop"""
        try:
            while self.running:
                # Handle events
                self.handle_events()
                
                # Update
                dt = self.renderer.tick(60)
                self.update(dt)
                
                # Render
                self.render()
        
        finally:
            # Save any remaining playtime before exiting
            current_time = time.time()
            elapsed = current_time - self.last_playtime_save
            if elapsed > 0:
                self.save_system.add_playtime(elapsed, "total")
            
            # Clean up
            self.renderer.quit()
            sys.exit(0)

