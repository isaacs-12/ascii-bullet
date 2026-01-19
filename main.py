#!/usr/bin/env python3
"""
ASCII Bullet Hell Game
Main entry point for the game
"""

import sys
import pygame
from src.core.game import Game


def main():
    """Initialize and run the game"""
    try:
        game = Game()
        game.run()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

