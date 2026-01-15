# ASCII Bullet Hell

A retro-styled bullet hell game with a terminal aesthetic, built in Python using pygame.

## Features

- **Terminal-style rendering** with ASCII graphics and custom frame
- **Interactive command-line interface** - type commands to control the game
- **Boot sequence animation** on startup
- **ASCII art title** - BLTHLL in glorious block letters
- **Command system** with multiple commands and easter eggs
- **Command history** - use UP/DOWN arrows to recall previous commands
- **Modular state-based architecture** ready for expansion

## Setup

1. Create and activate the virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Game

### Quick Start (Recommended)
```bash
./run.sh
```
The run script will automatically set up the virtual environment and dependencies if needed.

### Manual Run
```bash
source venv/bin/activate
python main.py
```

Or run directly:
```bash
./main.py
```

## Commands

Type these commands in the terminal:
- **start** / **new** - Begin a new game (coming soon)
- **continue** / **load** - Load saved game (coming soon)
- **quit** / **exit** - Exit the game
- **help** - Show available commands
- **about** - About this game
- **clear** - Clear the terminal
- **secret** - Check your easter egg progress

### Controls
- **Type** to enter commands
- **ENTER** - Execute command
- **BACKSPACE** - Delete characters
- **UP/DOWN** - Navigate command history
- **ESC** - Quick exit
- **Any key** - Skip boot sequence

## Project Structure

```
ascii-bullet/
├── main.py              # Game entry point
├── run.sh               # Quick start script
├── requirements.txt     # Python dependencies
├── src/
│   ├── game.py         # Main game controller
│   ├── terminal_renderer.py  # Terminal-style rendering system
│   ├── ascii_art.py    # ASCII art and text content
│   └── states/         # Game states
│       ├── base_state.py    # Base state class
│       └── main_menu.py     # Terminal command interface
```

## 🎨 Visual Design

The game window features:
- 80x50 character terminal display
- Retro green-on-black color scheme
- Custom frame with shadow effects
- Title bar with game name
- Large ASCII art title "BLTHLL"
- Animated boot sequence
- Interactive command prompt with blinking cursor

## 🥚 Easter Eggs & Hidden Content

There are hidden commands and responses throughout the terminal! The game includes a **fully navigable virtual filesystem** with secrets hidden in different directories.

**Explore the filesystem:**
- Use `ls` to see what's in your current directory
- Use `cd <directory>` to navigate (e.g., `cd data`, `cd weapons`)
- Use `cd ..` to go back to the parent directory
- Use `pwd` to see where you are
- Use `cat <filename>` to read files

**Other easter eggs to try:**
- Common terminal commands
- Pop culture references
- Be creative!

Type `secret` to check how many easter eggs you've found. The prompt shows your current directory - explore and find hidden files!

## Development Roadmap

- [x] Project setup with virtual environment
- [x] Terminal-style rendering system
- [x] Terminal command-line interface
- [x] Boot sequence animation
- [x] ASCII art title
- [x] Command parser with easter eggs
- [x] Quit functionality
- [ ] Save/Load system
- [ ] Game state implementation
- [ ] Player character and controls
- [ ] Bullet patterns and enemies
- [ ] Scoring system
- [ ] Sound effects and music
