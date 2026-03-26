"""ASCII art and text styling"""


# Large ASCII art for "BLTHLL" - using standard ASCII characters only
BLTHLL_ASCII = [
    r"      ########  ##        ##     ########  ##     ##  ##       ##",
    r"     ##     ## ##        ##        ##     ##     ##  ##       ##",
    r"    ##     ## ##        ##        ##     ##     ##  ##       ##",
    r"   ########  ##        ##        ##     #########  ##       ##",
    r"  ##     ## ##        ##        ##     ##     ##  ##       ##",
    r" ##     ## ##        ##        ##     ##     ##  ##       ##",
    r"########  ########  ########  ##     ##     ##  ######## ########",
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
        "[OK] Petting my dog...",
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
        "  start        - Begin a new game",
        "  quit         - Exit game",
        "  help         - Show this help",
        "  about        - About this game",
        "  clear        - Clear the terminal",
        "  highscores   - View top scores",
        "  stats        - View your statistics",
        "",
        "System commands:",
        "  top          - Interactive process viewer (press 'q' to quit)",
        "  ps           - Static process list",
        "  kill <pid>   - Terminate a process",
        "  systemctl    - Control systemd services",
        "    status <service>     - Show service status",
        "    start <service>      - Start a service",
        "    stop <service>       - Stop a service",
        "    enable <service>     - Enable a service (requires sudo)",
        "    disable <service>    - Disable a service (requires sudo)",
        "    list-units           - List all units",
        "    list-unit-files      - List all unit files",
        "",
        "Unix commands:",
        "  ls [path]    - List directory contents",
        "  ls -l        - List with permissions and details",
        "  cd <path>    - Change directory (TAB to complete)",
        "  cd ..        - Go to parent directory",
        "  pwd          - Print working directory",
        "  cat <file>   - Display file contents",
        "  head <file>  - Show first 10 lines of a file",
        "  tail <file>  - Show last 10 lines of a file",
        "  grep <p> <f> - Search for pattern in a file",
        "  wc <file>    - Count lines, words, and characters",
        "  find         - Search for files recursively",
        "  file <name>  - Identify file type",
        "  cp <s> <d>   - Copy a file",
        "  mv <s> <d>   - Move or rename a file",
        "  rm <file>    - Delete a file",
        "  rm -r <dir>  - Delete a directory recursively",
        "  mkdir <dir>  - Create a directory",
        "  rmdir <dir>  - Delete an empty directory",
        "  touch <file> - Create an empty file",
        "  chmod <m> <f> - Change file permissions",
        "  vim <file>   - Edit file (or 'vi', 'edit')",
        "  code         - Open VSCode-like editor",
        "  readme <f>   - View a markdown file with formatting",
        "  echo <text>  - Print text (use > or >> to write to file)",
        "  sudo <cmd>   - Execute command with root privileges",
        "  man <topic>  - View manual page (try: man ls, man python)",
        "  history      - Show command history",
        "  which <cmd>  - Show command location",
        "",
        "System info:",
        "  whoami       - Print current user",
        "  id           - Print user and group info",
        "  hostname     - Print system hostname",
        "  uname        - Print system name",
        "  date         - Print current date and time",
        "  uptime       - Print system uptime",
        "  env          - Print environment variables",
        "",
        "Scripting:",
        "  python <file> - Execute Python script (or 'run')",
        "",
        "Save management:",
        "  rm save      - Delete save file and reset everything",
        "  rm save --filesystem - Reset only filesystem",
        "  rm save --stats - Reset only game statistics",
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

