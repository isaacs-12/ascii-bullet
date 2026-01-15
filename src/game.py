"""Main game class"""

import sys
import pygame
from src.terminal_renderer import TerminalRenderer
from src.states.main_menu import MainMenuState
from src.save_system import SaveSystem


class Game:
    """Main game controller"""
    
    def __init__(self):
        """Initialize the game"""
        # Initialize save system
        self.save_system = SaveSystem()
        
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
        print(f"[DEBUG] Game.change_state() called, new_state={type(new_state).__name__}, call_enter={call_enter}")
        try:
            if self.current_state:
                print(f"[DEBUG] Exiting current state: {type(self.current_state).__name__}")
                self.current_state.exit()
            
            print(f"[DEBUG] Setting new state")
            self.current_state = new_state
            if call_enter:
                print(f"[DEBUG] Calling enter() on new state")
                self.current_state.enter()
            print(f"[DEBUG] State change completed successfully")
        except Exception as e:
            print(f"[ERROR] Exception in change_state: {e}")
            import traceback
            traceback.print_exc()
            raise
    
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
        print(f"[DEBUG] Game.render() called")
        if self.current_state:
            print(f"[DEBUG] Calling render on state: {type(self.current_state).__name__}")
            self.current_state.render()
            print(f"[DEBUG] State render completed")
    
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

