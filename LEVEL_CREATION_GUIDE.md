# Level Creation Guide

This guide shows you how to create new levels using the building block system.

## Basic Level Creation

### Step 1: Create a Level Configuration

```python
from src.level import LevelConfig

my_level = LevelConfig(
    width=100,        # Map width in cells
    height=60,        # Map height in cells
    seed=12345        # Random seed for reproducibility
)
```

### Step 2: Configure Difficulty

```python
# Enemy spawning
my_level.min_enemies = 5
my_level.max_enemies = 10
my_level.enemy_types = ['basic', 'fast', 'sniper']
my_level.spawn_interval = 5000  # ms between new enemy spawns
my_level.max_active_enemies = 15  # Maximum enemies on screen

# Difficulty multipliers
my_level.enemy_fire_rate_multiplier = 1.2  # Higher = faster firing
my_level.bullet_speed_multiplier = 1.0      # Higher = faster bullets
```

### Step 3: Add to Level List

In `src/level.py`, add your level configuration:

```python
MY_CUSTOM_LEVEL = LevelConfig(
    width=150,
    height=80,
    seed=99999
)
MY_CUSTOM_LEVEL.min_enemies = 8
MY_CUSTOM_LEVEL.max_enemies = 15
MY_CUSTOM_LEVEL.enemy_fire_rate_multiplier = 1.5
```

### Step 4: Launch Your Level

In `src/states/gameplay.py` or when creating the GameplayState:

```python
from src.level import MY_CUSTOM_LEVEL
from src.states.gameplay import GameplayState

# Pass your level config
game.change_state(GameplayState(game, level_config=MY_CUSTOM_LEVEL))
```

## Enemy Types

All enemies use the character `X` but are differentiated by color and behavior.

### Basic Enemy ('basic')
- Character: `X`
- Color: Red (255, 100, 100)
- Fire Rate: 2 seconds
- Bullet Speed: 12 cells/second
- Movement Speed: 2 cells/second
- Health: 20 shots
- Good for: Balanced difficulty

### Fast Enemy ('fast')
- Character: `X`
- Color: Orange (255, 150, 0)
- Fire Rate: 1 second
- Bullet Speed: 10 cells/second
- Movement Speed: 4 cells/second
- Health: 15 shots
- Good for: High pressure, many bullets, hard to predict

### Sniper Enemy ('sniper')
- Character: `X`
- Color: Purple (255, 0, 255)
- Fire Rate: 3 seconds
- Bullet Speed: 18 cells/second
- Movement Speed: 1 cell/second
- Health: 10 shots
- Good for: Dangerous but finite threat

**Note:** 
- Bullets inherit their enemy's color for visual clarity
- Enemies move around and bounce off walls
- Each shot costs 1 health - enemies disappear when exhausted
- New enemies spawn periodically from map edges

## Configuration Parameters

### Map Size
- `width`: Horizontal cells (recommend 80-200)
- `height`: Vertical cells (recommend 50-100)
- Larger maps = more room to dodge

### Enemy Count
- `min_enemies`: Initial enemies at level start
- `max_enemies`: Initial enemies at level start
- `max_active_enemies`: Maximum enemies on screen (includes spawned)
- `spawn_interval`: Milliseconds between new enemy spawns
- More enemies = higher difficulty

### Difficulty Multipliers
- `enemy_fire_rate_multiplier`: 
  - < 1.0: Slower firing (easier)
  - = 1.0: Normal
  - > 1.0: Faster firing (harder)
- `bullet_speed_multiplier`:
  - < 1.0: Slower bullets (easier)
  - = 1.0: Normal
  - > 1.0: Faster bullets (harder)

## Scoring System

Players earn points by getting close to bullets without being hit:
- **Within 4 tiles**: 5 points
- **Within 3 tiles**: 10 points
- **Within 2 tiles**: 25 points
- **Within 1 tile**: 50 points

Points are awarded once per bullet per distance tier, encouraging risky positioning.

## Example Levels

### Easy Beginner Level
```python
EASY_LEVEL = LevelConfig(width=80, height=50, seed=1111)
EASY_LEVEL.min_enemies = 2
EASY_LEVEL.max_enemies = 4
EASY_LEVEL.enemy_types = ['basic']
EASY_LEVEL.enemy_fire_rate_multiplier = 0.5
```

### Intense Challenge
```python
HARD_LEVEL = LevelConfig(width=120, height=70, seed=6666)
HARD_LEVEL.min_enemies = 10
HARD_LEVEL.max_enemies = 20
HARD_LEVEL.enemy_types = ['fast', 'sniper']
HARD_LEVEL.enemy_fire_rate_multiplier = 2.0
```

### Exploration Level (Large Map)
```python
EXPLORE_LEVEL = LevelConfig(width=200, height=120, seed=4242)
EXPLORE_LEVEL.min_enemies = 15
EXPLORE_LEVEL.max_enemies = 25
EXPLORE_LEVEL.enemy_types = ['basic', 'fast', 'sniper']
EXPLORE_LEVEL.enemy_fire_rate_multiplier = 1.0
```

## Tips for Level Design

1. **Start Small**: Test with small maps first (80x50)
2. **Balance Enemies**: Mix enemy types for variety
3. **Test Seeds**: Different seeds create different layouts
4. **Difficulty Curve**: Gradually increase multipliers between levels
5. **Space Matters**: Larger maps feel easier due to more dodge room

## Future Expansion Ideas

You can extend the system by:
- Adding new enemy types in `src/entities.py`
- Creating bullet patterns
- Adding obstacles or walls
- Implementing power-ups
- Creating boss enemies with special behaviors

