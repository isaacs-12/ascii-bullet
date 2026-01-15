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
- **highscores** - View top 10 high scores
- **stats** - View your statistics and progress
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
│   ├── script_executor.py   # Safe Python script execution
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

## 💾 Save System

The game **automatically saves** your progress:
- High scores (top 10)
- Secret commands discovered
- Filesystem exploration (directories visited, files read)
- Game statistics

Save file location: `~/.ascii-bullet/save.json`

## 🗂️ Dynamic Filesystem

The game features a **fully mutable filesystem** that you'll need to navigate and manipulate to solve puzzles!

**Read-only commands:**
- `ls` / `dir` - List directory contents
- `cd <dir>` - Change directory
- `pwd` - Print current directory
- `cat <file>` - Read file contents

**File operations:**
- `touch <file>` - Create empty file
- `echo text > file` - Write to file (overwrites)
- `echo text >> file` - Append to file
- `rm <file>` - Delete files (including default system files!)
- `mv <src> <dst>` - Move or rename files

**Directory operations:**
- `mkdir <dir>` - Create directory
- `rmdir <dir>` - Delete empty directory

**Script execution:**
- `python <file.py>` or `run <file.py>` - Execute Python scripts in a sandboxed environment

**Features:**
- **Persistent changes** - all modifications saved to `save.json`
- **Reset with** `rm save` - restores default filesystem if you get stuck
- **Tab completion** for `cd` and `cat`
- **Safe Python execution** - Write and run scripts to solve complex puzzles
- **16KB limit** for additional files (plenty of room for puzzle-solving!)

## 🥚 Easter Eggs & Hidden Content

There are hidden commands and responses throughout the terminal! The game includes a default filesystem with secrets to discover.

**Hints:**
- Try common terminal commands
- Look for pop culture references
- Explore the filesystem thoroughly
- Some puzzles may require writing code!

Type `secret` to check how many easter eggs you've found.

**You'll need these skills to solve puzzles:**
- Navigate and read files to find clues
- Move, create, and modify files to unlock secrets
- Write Python scripts to automate complex tasks
- Combine multiple tools to solve multi-step challenges

## 🐍 Python Scripting

Some puzzles may require writing Python scripts! Scripts run in a **sandboxed environment** with access to a safe game API.

**Example:**
```bash
# Try the example script
cd /home/pilot/blthll
python hello.py

# Or create your own
echo print('Hello World!') > test.py
python test.py
```

**Available API in scripts:**
- `game.read_file(filename)` - Read files from the filesystem
- `game.list_files()` - List files in current directory
- `game.get_pwd()` - Get current working directory
- `game.file_exists(filename)` - Check if file exists
- `print()` - Output to terminal
- Standard Python: `len()`, `range()`, `str()`, `int()`, `list()`, `dict()`, etc.

**Why you might need scripting:**
- Parse and analyze multiple files at once
- Search for patterns across the filesystem
- Decode or transform text programmatically
- Automate repetitive tasks
- Solve computational puzzles

**Safety features:**
- 5-second execution timeout
- Sandboxed execution (no real filesystem access)
- No dangerous imports blocked
- Only whitelisted Python operations allowed

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
- [x] Enemy movement and spawning
- [x] Proximity scoring system
- [x] Save/Load system (JSON-based)
- [x] High scores tracking
- [x] Statistics tracking
- [x] Mutable filesystem with file operations
- [x] Python script execution (sandboxed)
- [ ] More enemy types and patterns
- [ ] Multiple levels with progression
- [ ] Power-ups and abilities
- [ ] Sound effects and music
- [ ] Puzzle system using filesystem and scripts
