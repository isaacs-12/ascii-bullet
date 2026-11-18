"""Shared pytest setup: headless SDL and an isolated save directory."""

import os
import tempfile

# Must be set before pygame initialises anything.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
# Never touch the developer's real ~/.ascii-bullet save during tests.
os.environ["ASCII_BULLET_SAVE_DIR"] = tempfile.mkdtemp(prefix="ascii-bullet-test-")
