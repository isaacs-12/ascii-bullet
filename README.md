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
- **start** / **new** - Begin a new game
- **continue** / **load** - Load saved game (coming soon)
- **quit** / **exit** - Exit the game
- **help** - Show available commands
- **about** - About this game
- **clear** - Clear the terminal
- **secret** - Check your easter egg progress

### Terminal Controls
- **Type** to enter commands
- **ENTER** - Execute command
- **BACKSPACE** - Delete characters
- **UP/DOWN** - Navigate command history
- **ESC** - Quick exit
- **Any key** - Skip boot sequence

### Gameplay Controls
- **WASD** or **Arrow Keys** - Move player
- **ESC** or **Ctrl+C** - Return to menu

## Project Structure

```
ascii-bullet/
├── main.py                   # Game entry point
├── run.sh                    # Quick start script
├── requirements.txt          # Python dependencies
├── src/
│   ├── game.py              # Main game controller
│   ├── terminal_renderer.py # Terminal-style rendering system
│   ├── ascii_art.py         # ASCII art and text content
│   ├── filesystem.py        # Virtual filesystem for easter eggs
│   ├── entities.py          # Player, enemies, bullets
│   ├── camera.py            # Camera/viewport system
│   ├── level.py             # Level configuration and generation
│   └── states/              # Game states
│       ├── base_state.py    # Base state class
│       ├── main_menu.py     # Terminal command interface
│       └── gameplay.py      # Active gameplay state
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
- **Press TAB** after typing `cd` or `cat` for auto-completion!

**Other easter eggs to try:**
- Common terminal commands
- Pop culture references
- Be creative!

Type `secret` to check how many easter eggs you've found. The prompt shows your current directory - explore and find hidden files!

## 🎮 Gameplay

The game features a **bullet hell** dodging mechanic where you must survive waves of enemy fire!

**How to Play:**
1. Type `start` in the terminal to begin
2. Use **WASD** or **arrow keys** to move your character (o)
3. Dodge bullets (.) fired by enemies (X)
4. **Score points** by getting close to bullets without being hit!
   - Within 4 tiles: 5 points
   - Within 3 tiles: 10 points
   - Within 2 tiles: 25 points
   - Within 1 tile: 50 points
5. Survive and rack up the highest score!
6. Press **ESC** to return to the terminal menu

**Game Features:**
- **Proximity scoring system** - Rewards risky play by scoring points based on how close you get to bullets
- **Dynamic camera system** - The viewport follows your player and respects map boundaries
- **Moving enemies** - Enemies patrol the map and bounce off walls
- **Limited ammo system** - Enemies run out of health after shooting (20/15/10 shots)
- **Enemy spawning** - New enemies periodically spawn from map edges
- **Multiple enemy types** - Three enemy types (X) with different colors, speeds, and behaviors:
  - Red: Balanced (2 cells/s movement, 20 health)
  - Orange: Fast & aggressive (4 cells/s movement, 15 health)
  - Purple: Slow snipers (1 cell/s movement, 10 health, fast bullets)
- **Color-coded bullets** - Bullets inherit their shooter's color for visual clarity
- **Pseudorandom level generation** - Each playthrough is different but balanced
- **Configurable levels** - Easy to create new levels with custom parameters

## Development Roadmap

- [x] Project setup with virtual environment
- [x] Terminal-style rendering system
- [x] Terminal command-line interface
- [x] Boot sequence animation
- [x] ASCII art title
- [x] Command parser with easter eggs
- [x] Virtual filesystem navigation
- [x] Game state implementation
- [x] Player character and controls
- [x] Camera/viewport system
- [x] Bullet patterns and enemies
- [x] Level configuration system
- [ ] More enemy types and patterns
- [ ] Save/Load system
- [ ] Scoring and high scores
- [ ] Multiple levels with progression
- [ ] Power-ups and abilities
- [ ] Sound effects and music
