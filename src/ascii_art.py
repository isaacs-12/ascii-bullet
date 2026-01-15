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
        "",
        "Filesystem commands:",
        "  ls / dir    - List directory contents",
        "  cd <path>   - Change directory",
        "  cd ..       - Go to parent directory",
        "  pwd         - Print working directory",
        "  cat <file>  - Display file contents",
        "",
        "Hint: Explore the filesystem for secrets!",
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

