"""
Simulated filesystem for terminal easter eggs
"""


class VirtualFileSystem:
    """A virtual filesystem with directories and files"""
    
    def __init__(self):
        """Initialize the filesystem structure"""
        # Current directory path as a list (e.g., ['home', 'pilot', 'blthll'])
        self.current_path = ['home', 'pilot', 'blthll']
        
        # Filesystem structure: directories contain 'dirs' and 'files'
        # Files map to their content (string or list of strings)
        self.filesystem = {
            'home': {
                'dirs': {
                    'pilot': {
                        'dirs': {
                            'blthll': {
                                'dirs': {
                                    'weapons': {
                                        'dirs': {},
                                        'files': {
                                            'laser.txt': [
                                                "LASER CANNON v2.4",
                                                "Damage: High",
                                                "Fire Rate: Fast",
                                                "Special: Piercing shots"
                                            ],
                                            'missile.txt': [
                                                "HOMING MISSILES",
                                                "Damage: Very High",
                                                "Fire Rate: Slow",
                                                "Special: Tracks enemies"
                                            ]
                                        }
                                    },
                                    'data': {
                                        'dirs': {
                                            'secret': {
                                                'dirs': {},
                                                'files': {
                                                    'cheat_codes.txt': [
                                                        "SUPER SECRET CHEAT CODES",
                                                        "=======================",
                                                        "Up Up Down Down Left Right Left Right B A",
                                                        "Just kidding, no cheats here!",
                                                        "Git gud at dodging bullets instead."
                                                    ],
                                                    'developer_notes.txt': [
                                                        "TODO: Make bullets less impossible",
                                                        "TODO: Add easy mode (nah)",
                                                        "TODO: Increase bullet speed (yes!)",
                                                        "TODO: Add more particle effects"
                                                    ]
                                                }
                                            }
                                        },
                                        'files': {
                                            'bullets.dat': [
                                                "░▒▓█ BULLET DATA █▓▒░",
                                                "◉ ◎ ● ○ ◐ ◑ ◒ ◓ ◔ ◕",
                                                "",
                                                "Type: Standard",
                                                "Speed: Variable",
                                                "Pattern: Spiral, Linear, Radial"
                                            ],
                                            'highscores.txt': [
                                                "HIGH SCORES",
                                                "===========",
                                                "1. PLAYER1 - 999999",
                                                "2. HACKER  - 123456",
                                                "3. NOOB    - 00042"
                                            ]
                                        }
                                    },
                                    'certain_death': {
                                        'dirs': {},
                                        'files': {
                                            'warning.txt': [
                                                "⚠️  WARNING ⚠️",
                                                "",
                                                "You are entering the CERTAIN DEATH zone.",
                                                "Bullets here are UNAVOIDABLE.",
                                                "Turn back while you still can!",
                                                "",
                                                "...or don't. Your funeral. 💀"
                                            ]
                                        }
                                    }
                                },
                                'files': {
                                    'readme.txt': [
                                        "Welcome to BLTHLL (Bullet Hell)",
                                        "",
                                        "You are a pilot trying to survive.",
                                        "Good luck. You'll need it.",
                                        "",
                                        "Hint: Try exploring with 'ls' and 'cd'!"
                                    ],
                                    'manual.txt': [
                                        "SURVIVAL MANUAL",
                                        "===============",
                                        "Step 1: Don't get hit",
                                        "Step 2: See step 1",
                                        "Step 3: There is no step 3"
                                    ]
                                }
                            }
                        },
                        'files': {}
                    }
                },
                'files': {}
            },
            'etc': {
                'dirs': {},
                'files': {
                    'motd': [
                        "Welcome to BLTHLL Terminal System",
                        "Unauthorized access will result in more bullets."
                    ]
                }
            }
        }
    
    def get_current_directory(self):
        """Get the current directory object"""
        current = self.filesystem
        for i, dir_name in enumerate(self.current_path):
            if i == 0:
                # First level: directly in filesystem
                if dir_name in current:
                    current = current[dir_name]
                else:
                    return self.filesystem
            else:
                # Subsequent levels: navigate through 'dirs'
                if 'dirs' in current and dir_name in current['dirs']:
                    current = current['dirs'][dir_name]
                else:
                    return self.filesystem
        return current
    
    def get_pwd(self):
        """Get current working directory as string"""
        return '/' + '/'.join(self.current_path)
    
    def list_directory(self):
        """List contents of current directory"""
        current_dir = self.get_current_directory()
        contents = []
        
        # Add directories
        if 'dirs' in current_dir:
            for dir_name in sorted(current_dir['dirs'].keys()):
                contents.append(f"{dir_name}/")
        
        # Add files
        if 'files' in current_dir:
            for file_name in sorted(current_dir['files'].keys()):
                contents.append(file_name)
        
        return contents
    
    def change_directory(self, path):
        """
        Change directory
        
        Args:
            path: Directory path (e.g., 'data', '..', '/home/pilot')
            
        Returns:
            tuple: (success: bool, error_message: str or None)
        """
        if path == '..':
            # Go to parent directory
            if len(self.current_path) > 1:
                self.current_path.pop()
                return (True, None)
            else:
                return (False, "Already at root directory")
        
        elif path == '/' or path == '~':
            # Go to home
            self.current_path = ['home', 'pilot', 'blthll']
            return (True, None)
        
        elif path.startswith('/'):
            # Absolute path
            parts = [p for p in path.split('/') if p]
            if self._directory_exists(parts):
                self.current_path = parts
                return (True, None)
            else:
                return (False, f"cd: {path}: No such directory")
        
        else:
            # Relative path
            new_path = self.current_path + [path]
            if self._directory_exists(new_path):
                self.current_path = new_path
                return (True, None)
            else:
                return (False, f"cd: {path}: No such directory")
    
    def _directory_exists(self, path_list):
        """Check if a directory path exists"""
        current = self.filesystem
        for i, dir_name in enumerate(path_list):
            if i == 0:
                # First level: directly in filesystem
                if dir_name in current:
                    current = current[dir_name]
                else:
                    return False
            else:
                # Subsequent levels: navigate through 'dirs'
                if 'dirs' in current and dir_name in current['dirs']:
                    current = current['dirs'][dir_name]
                else:
                    return False
        return True
    
    def read_file(self, filename):
        """
        Read a file from the current directory
        
        Args:
            filename: Name of the file to read
            
        Returns:
            tuple: (success: bool, content: list of strings or error message)
        """
        current_dir = self.get_current_directory()
        
        if 'files' in current_dir and filename in current_dir['files']:
            content = current_dir['files'][filename]
            if isinstance(content, list):
                return (True, content)
            else:
                return (True, [content])
        else:
            return (False, f"cat: {filename}: No such file")
    
    def file_exists(self, filename):
        """Check if a file exists in the current directory"""
        current_dir = self.get_current_directory()
        return 'files' in current_dir and filename in current_dir['files']

