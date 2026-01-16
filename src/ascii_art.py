"""ASCII art and text styling"""


# Large ASCII art for "BLTHLL" - using standard ASCII characters only
BLTHLL_ASCII = [
    r"########  ##       ########  ##     ##  ##       ##",
    r"##     ## ##          ##     ##     ##  ##       ##",
    r"##     ## ##          ##     #########  ##       ##",
    r"########  ##          ##     ##     ##  ##       ##",
    r"##     ## ##          ##     ##     ##  ##       ##",
    r"########  ########    ##     ##     ##  ######## ########",
]


def get_startup_sequence():
    """Get the startup boot sequence text"""
    return [
        "INITIALIZING BLTHLL SYSTEM...",
        "",
        "[OK] Loading core modules...",
        "[OK] Initializing bullet patterns...",
        "[OK] Loading player systems...",
        "[OK] Checking save data...",
        "",
        "System ready.",
        "",
    ]


def get_welcome_text():
    """Get welcome message"""
    return [
        "Welcome to BULLET HELL Terminal",
        "Type 'help' for available commands",
        "",
    ]


def get_help_text():
    """Get help command output"""
    return [
        "Available commands:",
        "  start       - Begin a new game",
        "  continue    - Load saved game",
        "  quit        - Exit game",
        "  help        - Show this help",
        "  about       - About this game",
        "  clear       - Clear the terminal",
        "  highscores  - View top scores",
        "  stats       - View your statistics",
        "",
        "System commands:",
        "  top         - Interactive process viewer (press 'q' to quit)",
        "  ps          - Static process list",
        "  kill <pid>  - Terminate a process",
        "",
        "Filesystem commands:",
        "  ls / dir       - List directory contents",
        "  cd <path>      - Change directory (TAB to complete)",
      "  cd ..          - Go to parent directory",
      "  pwd            - Print working directory",
      "  cat <file>     - Display file contents (TAB to complete)",
      "  vim <file>     - Edit file (or 'vi' or 'edit')",
      "  touch <file>   - Create empty file",
        "  mkdir <dir>    - Create directory",
        "  rm <file>      - Delete file",
        "  rm save        - Delete save file and reset local filesystem",
        "  rmdir <dir>    - Delete empty directory",
      "  mv <src> <dst> - Move or rename file",
      "  chmod <m> <f>  - Change file permissions",
      "  ls -l          - List files with permissions",
      "  sudo <cmd>     - Execute command with root privileges",
      "  echo text > f  - Write to file (overwrites)",
      "  echo text >> f - Append to file",
      "  python <file>  - Execute Python script (or 'run')",
        "",
    ]


def get_about_text():
    """Get about text"""
    return [
        "BLTHLL (Bullet Hell) v0.1.0",
        "A terminal-based bullet hell adventure",
        "",
        "Survive waves of bullets in ASCII glory!",
        "",
    ]

