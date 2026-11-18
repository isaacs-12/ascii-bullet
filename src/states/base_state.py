"""Base state class for game states"""


class BaseState:
    """Base class for all game states"""

    def __init__(self, game):
        """
        Initialize the state

        Args:
            game: Reference to the main game object
        """
        self.game = game
        self.renderer = game.renderer

    def handle_events(self, events):
        """
        Handle pygame events

        Args:
            events: List of pygame events
        """
        pass

    def update(self, dt):
        """
        Update state logic

        Args:
            dt: Delta time in milliseconds
        """
        pass

    def render(self):
        """Render the state to the terminal"""
        pass

    def enter(self):
        """Called when entering this state"""
        pass

    def exit(self):
        """Called when exiting this state"""
        pass

