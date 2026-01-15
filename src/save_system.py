"""
Save system for persistent game data
"""

import json
import os
from pathlib import Path
from datetime import datetime


class SaveSystem:
    """Manages saving and loading game data"""
    
    def __init__(self):
        """Initialize save system"""
        # Get save file location (in user's home directory)
        home = Path.home()
        self.save_dir = home / ".ascii-bullet"
        self.save_file = self.save_dir / "save.json"
        
        # Ensure save directory exists
        self.save_dir.mkdir(exist_ok=True)
        
        # Load or initialize save data
        self.data = self._load()
    
    def _load(self):
        """Load save data from file"""
        if self.save_file.exists():
            try:
                with open(self.save_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                # Corrupted save file, start fresh
                return self._default_save_data()
        else:
            return self._default_save_data()
    
    def _default_save_data(self):
        """Get default save data structure"""
        return {
            "version": "0.1.0",
            "created": datetime.now().isoformat(),
            "last_played": datetime.now().isoformat(),
            
            # Scores
            "high_scores": [],  # List of {score, time, date}
            "total_games_played": 0,
            "total_time_survived": 0,
            
            # Discoveries
            "secret_commands_found": [],  # List of secret command IDs
            "filesystem_explored": {
                "directories_visited": [],
                "files_read": []
            },
            
            # Stats
            "stats": {
                "bullets_dodged": 0,
                "closest_call": 999,  # Closest distance to a bullet
                "enemies_depleted": 0,  # Enemies that ran out of ammo
            },
            
            # Settings
            "settings": {
                "terminal_width": 80,
                "terminal_height": 50,
                "font_size": 12,
            },
            
            # Filesystem state
            "filesystem": None  # Will store user modifications
        }
    
    def save(self):
        """Write save data to file"""
        self.data["last_played"] = datetime.now().isoformat()
        
        try:
            with open(self.save_file, 'w') as f:
                json.dump(self.data, f, indent=2)
            return True
        except IOError:
            return False
    
    # High Scores
    def add_score(self, score, time_survived):
        """
        Add a score to high scores list
        
        Args:
            score: Final score
            time_survived: Time survived in milliseconds
        """
        entry = {
            "score": score,
            "time": time_survived,
            "date": datetime.now().isoformat()
        }
        
        self.data["high_scores"].append(entry)
        
        # Sort by score descending
        self.data["high_scores"].sort(key=lambda x: x["score"], reverse=True)
        
        # Keep only top 10
        self.data["high_scores"] = self.data["high_scores"][:10]
        
        self.data["total_games_played"] += 1
        self.data["total_time_survived"] += time_survived
        
        self.save()
    
    def get_high_scores(self, limit=10):
        """Get top high scores"""
        return self.data["high_scores"][:limit]
    
    def is_high_score(self, score):
        """Check if score makes it to top 10"""
        if len(self.data["high_scores"]) < 10:
            return True
        return score > self.data["high_scores"][-1]["score"]
    
    # Secret Commands
    def add_secret_found(self, secret_id):
        """Record a secret command being found"""
        if secret_id not in self.data["secret_commands_found"]:
            self.data["secret_commands_found"].append(secret_id)
            self.save()
            return True  # Newly found
        return False  # Already found
    
    def get_secrets_found(self):
        """Get list of found secret command IDs"""
        return self.data["secret_commands_found"]
    
    def get_secret_count(self):
        """Get number of secrets found"""
        return len(self.data["secret_commands_found"])
    
    # Filesystem Exploration
    def mark_directory_visited(self, path):
        """Record a directory being visited"""
        if path not in self.data["filesystem_explored"]["directories_visited"]:
            self.data["filesystem_explored"]["directories_visited"].append(path)
            self.save()
    
    def mark_file_read(self, filepath):
        """Record a file being read"""
        if filepath not in self.data["filesystem_explored"]["files_read"]:
            self.data["filesystem_explored"]["files_read"].append(filepath)
            self.save()
    
    def get_exploration_stats(self):
        """Get exploration statistics"""
        return {
            "dirs_visited": len(self.data["filesystem_explored"]["directories_visited"]),
            "files_read": len(self.data["filesystem_explored"]["files_read"])
        }
    
    # Stats
    def update_stat(self, stat_name, value):
        """
        Update a statistic
        
        Args:
            stat_name: Name of stat to update
            value: New value (or increment for some stats)
        """
        if stat_name in self.data["stats"]:
            if stat_name == "closest_call":
                # Keep the closest distance
                self.data["stats"][stat_name] = min(self.data["stats"][stat_name], value)
            else:
                # For counters, add to existing
                self.data["stats"][stat_name] += value
            self.save()
    
    def get_stat(self, stat_name):
        """Get a specific stat"""
        return self.data["stats"].get(stat_name, 0)
    
    def get_all_stats(self):
        """Get all statistics"""
        return self.data["stats"].copy()
    
    # Settings
    def update_setting(self, setting_name, value):
        """Update a setting"""
        if setting_name in self.data["settings"]:
            self.data["settings"][setting_name] = value
            self.save()
    
    def get_setting(self, setting_name, default=None):
        """Get a setting value"""
        return self.data["settings"].get(setting_name, default)
    
    # Utility
    def get_save_location(self):
        """Get the save file path as a string"""
        return str(self.save_file)
    
    # Filesystem State
    def save_filesystem(self, filesystem_state):
        """Save filesystem state"""
        self.data["filesystem"] = filesystem_state
        self.save()
    
    def get_filesystem_state(self):
        """Get saved filesystem state"""
        return self.data.get("filesystem", None)
    
    def reset_save(self):
        """Reset all save data (destructive!)"""
        self.data = self._default_save_data()
        self.save()
    
    def export_save(self, filepath):
        """Export save data to a specific file"""
        try:
            with open(filepath, 'w') as f:
                json.dump(self.data, f, indent=2)
            return True
        except IOError:
            return False

