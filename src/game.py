"""Main game class"""

import sys
import pygame
from src.terminal_renderer import TerminalRenderer
from src.states.main_menu import MainMenuState


class Game:
    """Main game controller"""
    
    def __init__(self):
        """Initialize the game"""
        # Create terminal renderer
        self.renderer = TerminalRenderer(width=80, height=50, cell_size=12)
        
        # Game state
        self.running = True
        self.current_state = None
        
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
            # Clean up
            self.renderer.quit()
            sys.exit(0)

