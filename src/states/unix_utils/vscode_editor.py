"""
VSCode-like text editor for the virtual filesystem
Minimal terminal UI with sidebar, tabs, and syntax highlighting
"""

import pygame

from src.states.base_state import BaseState


class VSCodeEditorState(BaseState):
    """A minimal VSCode-like editor with sidebar and tabs"""

    def __init__(self, game, filesystem, previous_state):
        """
        Initialize the VSCode-like editor

        Args:
            game: Game instance
            filesystem: VirtualFileSystem instance
            previous_state: State to return to when done (MainMenuState for command execution)
        """
        super().__init__(game)
        self.filesystem = filesystem
        self.previous_state = previous_state  # MainMenuState for command execution

        # Sidebar state
        self.sidebar_width = 20  # Character width of sidebar
        self.sidebar_drag_x = None  # X position when dragging (None if not dragging)
        self.sidebar_min_width = 10
        self.sidebar_max_width = 40

        # File tree state
        self.expanded_dirs = set()  # Set of expanded directory paths
        self.selected_file = None  # Currently selected file in sidebar

        # Search state (for searching within files)
        self.search_query = ""  # Current search query for content search
        self.search_results = []  # List of (filepath, line_num, line_text) matching search
        self.search_cursor = 0  # Currently selected search result index

        # Sidebar tab state
        self.sidebar_tab = "files"  # "files" or "search"

        # Quick open state (Cmd+P modal)
        self.quick_open_active = False  # Whether quick open dialog is shown
        self.quick_open_query = ""  # Current search query for files
        self.quick_open_results = []  # List of matching filepaths
        self.quick_open_cursor = 0  # Currently selected result index

        # Tab system
        self.open_tabs = []  # List of (filename, full_path) tuples
        self.active_tab_index = 0  # Index of currently active tab

        # Editor state for active tab
        self.editor_scroll_y = 0  # Vertical scroll position (line offset)
        self.cursor_line = 0
        self.cursor_col = 0

        # Text selection state
        self.selection_start = None  # (line, col) or None if no selection
        self.selection_end = None    # (line, col) or None if no selection

        # File contents cache: full_path -> list of lines
        self.file_contents = {}

        # Initialize with current directory expanded
        current_path = self.filesystem.get_pwd()
        self.expanded_dirs.add(current_path)

        # Message/status
        self.status_message = "Code Editor | ESC to quit | Click files to open"
        self.status_message_timeout = 0

        # Clipboard for copy/paste
        self.clipboard = []

        # Key repeat tracking for arrow keys
        self.key_repeat_state = {}  # key -> (last_press_time, repeat_count)
        self.key_repeat_delay = 200  # ms before first repeat
        self.key_repeat_interval = 30  # ms between repeats

        # Terminal state
        self.terminal_open = False
        self.terminal_height = 8  # Height in character lines (minimum 3)
        self.terminal_min_height = 3
        self.terminal_max_height = self.renderer.char_height - 10  # Leave room for editor
        self.terminal_drag_y = None  # Y position when dragging terminal divider (None if not dragging)
        self.terminal_output_lines = []  # Terminal output buffer
        self.terminal_input_buffer = ""  # Current input in terminal
        self.terminal_cursor_visible = True
        self.terminal_cursor_timer = 0
        self.terminal_scroll_offset = 0  # Scroll offset for terminal output
        # Load command history from save system (same as main menu)
        saved_history = game.save_system.get_command_history()
        self.terminal_history = saved_history.copy() if saved_history else []
        self.terminal_history_index = -1

        # Focus tracking: 'editor' or 'terminal' (None means editor when terminal closed)
        self.focused_area = 'editor'  # Default to editor

    def enter(self):
        """Called when entering this state"""
        pass

    def exit(self):
        """Called when exiting this state"""
        # Auto-save all open files
        self._save_all_files()

    def _save_all_files(self):
        """Save all open files"""
        for _filename, full_path in self.open_tabs:
            if full_path in self.file_contents:
                self._save_file(full_path, self.file_contents[full_path])

    def _save_file(self, full_path, lines):
        """Save file content to filesystem"""
        # Extract filename from full path
        filename = full_path.split('/')[-1]

        # Get current directory for this file
        path_parts = full_path.strip('/').split('/')
        if len(path_parts) > 1:
            dir_path = '/' + '/'.join(path_parts[:-1])
            old_path = self.filesystem.current_path[:]
            self.filesystem.change_directory(dir_path)
            filename = path_parts[-1]
        else:
            filename = path_parts[0] if path_parts else filename

        # Write file
        try:
            ok, current = self.filesystem.read_file(filename)
            if ok and [str(x) for x in current] == list(lines):
                return  # unchanged: don't turn a default file into a user-modified copy
            if self.filesystem.file_exists(filename):
                # Update existing file
                self.filesystem.write_file(filename, lines, append=False)
            else:
                # Create new file
                self.filesystem.create_file(filename, lines)
        except Exception as e:
            print(f"Error saving file {full_path}: {e}")
        finally:
            if len(path_parts) > 1:
                self.filesystem.current_path = old_path

    def _get_file_tree(self):
        """Get file tree structure for current directory"""
        current_path = self.filesystem.get_pwd()
        current_dir = self.filesystem.get_current_directory()

        tree = []

        # Helper to recursively build tree
        def build_tree(dir_path, dir_node, depth=0):
            # Add directories first
            if 'dirs' in dir_node:
                for dir_name in sorted(dir_node['dirs'].keys()):
                    full_dir_path = f"{dir_path}/{dir_name}" if dir_path != "/" else f"/{dir_name}"
                    is_expanded = full_dir_path in self.expanded_dirs

                    # Directory indicator
                    prefix = "  " * depth
                    if is_expanded:
                        indicator = "- "
                    else:
                        indicator = "+ "

                    tree.append({
                        'type': 'dir',
                        'name': dir_name,
                        'path': full_dir_path,
                        'depth': depth,
                        'expanded': is_expanded,
                        'display': f"{prefix}{indicator}{dir_name}/"
                    })

                    # If expanded, add children
                    if is_expanded:
                        subdir_node = dir_node['dirs'][dir_name]
                        build_tree(full_dir_path, subdir_node, depth + 1)

            # Add files
            if 'files' in dir_node:
                for file_name in sorted(dir_node['files'].keys()):
                    full_file_path = f"{dir_path}/{file_name}" if dir_path != "/" else f"/{file_name}"

                    # Check if file was deleted
                    if full_file_path in self.filesystem.user_deleted_files:
                        continue

                    prefix = "  " * depth
                    tree.append({
                        'type': 'file',
                        'name': file_name,
                        'path': full_file_path,
                        'depth': depth,
                        'display': f"{prefix}  {file_name}"
                    })

            # Add user-created directories
            for user_dir in sorted(self.filesystem.user_created_dirs):
                user_dir_clean = user_dir.rstrip("/")
                # Check if this directory is a direct child of dir_path
                if dir_path == "/":
                    # At root, check if it's a top-level directory
                    if user_dir_clean.startswith("/") and user_dir_clean.count("/") == 1:
                        dir_name = user_dir_clean[1:]  # Remove leading /
                        full_dir_path = user_dir_clean
                        is_expanded = full_dir_path in self.expanded_dirs

                        prefix = "  " * depth
                        if is_expanded:
                            indicator = "▼ "
                        else:
                            indicator = "▶ "

                        tree.append({
                            'type': 'dir',
                            'name': dir_name,
                            'path': full_dir_path,
                            'depth': depth,
                            'expanded': is_expanded,
                            'display': f"{prefix}{indicator}{dir_name}/"
                        })
                else:
                    # Not at root
                    expected_prefix = dir_path + "/"
                    if user_dir_clean.startswith(expected_prefix):
                        remaining = user_dir_clean[len(expected_prefix):]
                        if "/" not in remaining:  # Direct child
                            dir_name = remaining
                            full_dir_path = user_dir_clean
                            is_expanded = full_dir_path in self.expanded_dirs

                            prefix = "  " * depth
                            if is_expanded:
                                indicator = "▼ "
                            else:
                                indicator = "▶ "

                            tree.append({
                                'type': 'dir',
                                'name': dir_name,
                                'path': full_dir_path,
                                'depth': depth,
                                'expanded': is_expanded,
                                'display': f"{prefix}{indicator}{dir_name}/"
                            })

            # Add user-created files
            for user_file_path in sorted(self.filesystem.user_created_files.keys()):
                # Check if this file is a direct child of dir_path
                if dir_path == "/":
                    # At root, check if it's a top-level file
                    if user_file_path.startswith("/") and user_file_path.count("/") == 1:
                        file_name = user_file_path[1:]  # Remove leading /
                        prefix = "  " * depth
                        tree.append({
                            'type': 'file',
                            'name': file_name,
                            'path': user_file_path,
                            'depth': depth,
                            'display': f"{prefix}  {file_name}"
                        })
                else:
                    # Not at root
                    expected_prefix = dir_path + "/"
                    if user_file_path.startswith(expected_prefix):
                        remaining = user_file_path[len(expected_prefix):]
                        if "/" not in remaining:  # Direct child
                            file_name = remaining
                            prefix = "  " * depth
                            tree.append({
                                'type': 'file',
                                'name': file_name,
                                'path': user_file_path,
                                'depth': depth,
                                'display': f"{prefix}  {file_name}"
                            })

            # Add user-modified files
            for user_file_path in sorted(self.filesystem.user_modified_files.keys()):
                # Skip if already added
                if any(item['path'] == user_file_path for item in tree):
                    continue

                # Check if this file is a direct child of dir_path
                if dir_path == "/":
                    # At root, check if it's a top-level file
                    if user_file_path.startswith("/") and user_file_path.count("/") == 1:
                        file_name = user_file_path[1:]  # Remove leading /
                        prefix = "  " * depth
                        tree.append({
                            'type': 'file',
                            'name': file_name,
                            'path': user_file_path,
                            'depth': depth,
                            'display': f"{prefix}  {file_name}"
                        })
                else:
                    # Not at root
                    expected_prefix = dir_path + "/"
                    if user_file_path.startswith(expected_prefix):
                        remaining = user_file_path[len(expected_prefix):]
                        if "/" not in remaining:  # Direct child
                            file_name = remaining
                            prefix = "  " * depth
                            tree.append({
                                'type': 'file',
                                'name': file_name,
                                'path': user_file_path,
                                'depth': depth,
                                'display': f"{prefix}  {file_name}"
                            })

        # Start building from current directory
        if current_path == "/":
            # At root, iterate over top-level directories
            for top_level in sorted(current_dir.keys()):
                if top_level in current_dir:
                    node = current_dir[top_level]
                    if isinstance(node, dict):
                        # Build tree for this top-level directory
                        full_dir_path = f"/{top_level}"
                        is_expanded = full_dir_path in self.expanded_dirs

                        # Add directory to tree
                        tree.append({
                            'type': 'dir',
                            'name': top_level,
                            'path': full_dir_path,
                            'depth': 0,
                            'expanded': is_expanded,
                            'display': f"{'- ' if is_expanded else '+ '}{top_level}/"
                        })

                        # If expanded, add children
                        if is_expanded:
                            build_tree(full_dir_path, node, 1)
        else:
            build_tree(current_path, current_dir, 0)

        return tree

    def _search_files(self, query):
        """Search for files matching the query in current working directory and subdirectories"""
        if not query.strip():
            self.search_results = []
            return

        query_lower = query.lower()
        results = []
        base_path = self.filesystem.get_pwd()

        # Helper to recursively search through filesystem
        def search_dir(dir_path, dir_node, max_depth=10, current_depth=0):
            if current_depth > max_depth:
                return

            # Search files
            if 'files' in dir_node:
                for file_name in sorted(dir_node['files'].keys()):
                    if query_lower in file_name.lower():
                        full_path = f"{dir_path}/{file_name}" if dir_path != "/" else f"/{file_name}"
                        if full_path not in self.filesystem.user_deleted_files:
                            results.append((full_path, file_name))

            # Search directories
            if 'dirs' in dir_node:
                for dir_name in sorted(dir_node['dirs'].keys()):
                    full_dir_path = f"{dir_path}/{dir_name}" if dir_path != "/" else f"/{dir_name}"
                    if query_lower in dir_name.lower():
                        results.append((full_dir_path, f"{dir_name}/"))

                    # Recursively search subdirectory
                    subdir_node = dir_node['dirs'][dir_name]
                    search_dir(full_dir_path, subdir_node, max_depth, current_depth + 1)

            # Search user-created directories
            for user_dir in sorted(self.filesystem.user_created_dirs):
                user_dir_clean = user_dir.rstrip("/")
                expected_prefix = dir_path + "/" if dir_path != "/" else "/"

                if user_dir_clean.startswith(expected_prefix):
                    remaining = user_dir_clean[len(expected_prefix):]
                    if "/" not in remaining:  # Direct child
                        if query_lower in remaining.lower():
                            results.append((user_dir_clean, f"{remaining}/"))

            # Search user-created and user-modified files
            for user_file_path in sorted(self.filesystem.user_created_files):
                expected_prefix = dir_path + "/" if dir_path != "/" else "/"

                if user_file_path.startswith(expected_prefix):
                    remaining = user_file_path[len(expected_prefix):]
                    if "/" not in remaining and query_lower in remaining.lower():
                        results.append((user_file_path, remaining))

            for user_file_path in sorted(self.filesystem.user_modified_files.keys()):
                expected_prefix = dir_path + "/" if dir_path != "/" else "/"

                if user_file_path.startswith(expected_prefix):
                    remaining = user_file_path[len(expected_prefix):]
                    if "/" not in remaining and query_lower in remaining.lower():
                        if not any(r[0] == user_file_path for r in results):
                            results.append((user_file_path, remaining))

        # Start search from base path
        try:
            current_dir = self.filesystem.get_current_directory()
            search_dir(base_path, current_dir)
        except Exception:
            pass

        # Remove duplicates while preserving order
        seen = set()
        unique_results = []
        for path, name in results:
            if path not in seen:
                seen.add(path)
                unique_results.append((path, name))

        self.search_results = unique_results
        self.search_cursor = 0

    def _toggle_search(self):
        """Toggle between files and search tabs"""
        if self.sidebar_tab == "files":
            self.sidebar_tab = "search"
            self.search_query = ""
            self.search_results = []
            self.search_cursor = 0
        else:
            self.sidebar_tab = "files"
            self.search_query = ""
            self.search_results = []

    def _toggle_quick_open(self):
        """Toggle quick open modal dialog"""
        self.quick_open_active = not self.quick_open_active
        if self.quick_open_active:
            self.quick_open_query = ""
            self.quick_open_results = []
            self.quick_open_cursor = 0
        else:
            self.quick_open_query = ""
            self.quick_open_results = []

    def _search_file_content(self, query):
        """Search for text within files in current directory"""
        if not query.strip():
            self.search_results = []
            return

        query_lower = query.lower()
        # Group results by file: {filepath: [(line_num, line_text), ...]}
        file_results = {}
        base_path = self.filesystem.get_pwd()

        # Helper to recursively search files in filesystem
        def search_dir(dir_path, dir_node, max_depth=10, current_depth=0):
            if current_depth > max_depth:
                return

            # Search files in directory
            if 'files' in dir_node:
                for file_name in sorted(dir_node['files'].keys()):
                    full_path = f"{dir_path}/{file_name}" if dir_path != "/" else f"/{file_name}"
                    if full_path not in self.filesystem.user_deleted_files:
                        # Try to read file content
                        try:
                            success, content = self.filesystem.read_file(file_name)
                            if success:
                                if isinstance(content, list):
                                    lines = content
                                else:
                                    lines = str(content).split('\n')

                                matches = []
                                for line_num, line_text in enumerate(lines):
                                    if query_lower in line_text.lower():
                                        matches.append((line_num, line_text.strip()))

                                if matches:
                                    file_results[full_path] = matches
                        except Exception:
                            pass

            # Recursively search subdirectories
            if 'dirs' in dir_node:
                for dir_name in sorted(dir_node['dirs'].keys()):
                    full_dir_path = f"{dir_path}/{dir_name}" if dir_path != "/" else f"/{dir_name}"
                    subdir_node = dir_node['dirs'][dir_name]
                    # Save current directory, navigate, search, restore
                    saved_path = self.filesystem.current_path[:]
                    try:
                        self.filesystem.change_directory(full_dir_path)
                        search_dir(full_dir_path, subdir_node, max_depth, current_depth + 1)
                    except Exception:
                        pass
                    finally:
                        self.filesystem.current_path = saved_path

        # Start search from base path
        try:
            saved_path = self.filesystem.current_path[:]
            self.filesystem.change_directory(base_path)
            current_dir = self.filesystem.get_current_directory()
            search_dir(base_path, current_dir)
            self.filesystem.current_path = saved_path
        except Exception:
            pass

        # Convert to flat list with file headers: [('file', path), ('match', path, line_num, line_text), ...]
        results = []
        for filepath in sorted(file_results.keys()):
            results.append(('file', filepath))
            for line_num, line_text in file_results[filepath]:
                results.append(('match', filepath, line_num, line_text))

        self.search_results = results
        self.search_cursor = 0

    def _search_files_quick_open(self, query):
        """Search for files by name (for quick open)"""
        if not query.strip():
            self.quick_open_results = []
            return

        query_lower = query.lower()
        results = []
        base_path = self.filesystem.get_pwd()

        # Helper to recursively search through filesystem
        def search_dir(dir_path, dir_node, max_depth=10, current_depth=0):
            if current_depth > max_depth:
                return

            # Search files
            if 'files' in dir_node:
                for file_name in sorted(dir_node['files'].keys()):
                    if query_lower in file_name.lower():
                        full_path = f"{dir_path}/{file_name}" if dir_path != "/" else f"/{file_name}"
                        if full_path not in self.filesystem.user_deleted_files:
                            results.append(full_path)

            # Search directories
            if 'dirs' in dir_node:
                for dir_name in sorted(dir_node['dirs'].keys()):
                    full_dir_path = f"{dir_path}/{dir_name}" if dir_path != "/" else f"/{dir_name}"
                    if query_lower in dir_name.lower():
                        results.append(full_dir_path + "/")

                    # Recursively search subdirectory
                    subdir_node = dir_node['dirs'][dir_name]
                    search_dir(full_dir_path, subdir_node, max_depth, current_depth + 1)

            # Search user-created directories
            for user_dir in sorted(self.filesystem.user_created_dirs):
                user_dir_clean = user_dir.rstrip("/")
                expected_prefix = dir_path + "/" if dir_path != "/" else "/"

                if user_dir_clean.startswith(expected_prefix):
                    remaining = user_dir_clean[len(expected_prefix):]
                    if "/" not in remaining and query_lower in remaining.lower():
                        results.append(user_dir_clean + "/")

            # Search user-created and user-modified files
            for user_file_path in sorted(self.filesystem.user_created_files):
                expected_prefix = dir_path + "/" if dir_path != "/" else "/"

                if user_file_path.startswith(expected_prefix):
                    remaining = user_file_path[len(expected_prefix):]
                    if "/" not in remaining and query_lower in remaining.lower():
                        results.append(user_file_path)

            for user_file_path in sorted(self.filesystem.user_modified_files.keys()):
                expected_prefix = dir_path + "/" if dir_path != "/" else "/"

                if user_file_path.startswith(expected_prefix):
                    remaining = user_file_path[len(expected_prefix):]
                    if "/" not in remaining and query_lower in remaining.lower():
                        if not any(r == user_file_path for r in results):
                            results.append(user_file_path)

        # Start search from base path
        try:
            current_dir = self.filesystem.get_current_directory()
            search_dir(base_path, current_dir)
        except Exception:
            pass

        # Remove duplicates while preserving order
        seen = set()
        unique_results = []
        for path in results:
            if path not in seen:
                seen.add(path)
                unique_results.append(path)

        self.quick_open_results = unique_results
        self.quick_open_cursor = 0

    def _open_file(self, full_path, filename):
        for i, (_name, path) in enumerate(self.open_tabs):
            if path == full_path:
                self.active_tab_index = i
                return

        # Load file content
        path_parts = full_path.strip('/').split('/')
        if len(path_parts) > 1:
            dir_path = '/' + '/'.join(path_parts[:-1])
            old_path = self.filesystem.current_path[:]
            self.filesystem.change_directory(dir_path)
            file_to_read = path_parts[-1]
        else:
            file_to_read = path_parts[0] if path_parts else filename

        success, content = self.filesystem.read_file(file_to_read)
        if success:
            if isinstance(content, list):
                lines = [str(line) for line in content]
            else:
                lines = [str(content)]
        else:
            # New file
            lines = [""]

        # Restore path
        if len(path_parts) > 1:
            self.filesystem.current_path = old_path

        # Add to tabs
        self.open_tabs.append((filename, full_path))
        self.active_tab_index = len(self.open_tabs) - 1
        self.file_contents[full_path] = lines

        # Reset editor state
        self.cursor_line = 0
        self.cursor_col = 0
        self.editor_scroll_y = 0

    def _close_tab(self, index):
        """Close a tab"""
        if 0 <= index < len(self.open_tabs):
            filename, full_path = self.open_tabs[index]

            # Auto-save before closing
            if full_path in self.file_contents:
                self._save_file(full_path, self.file_contents[full_path])

            # Remove from tabs
            del self.open_tabs[index]
            if full_path in self.file_contents:
                del self.file_contents[full_path]

            # Adjust active tab index
            if self.active_tab_index >= len(self.open_tabs):
                self.active_tab_index = max(0, len(self.open_tabs) - 1)
            elif self.active_tab_index > index:
                self.active_tab_index -= 1

            # If no tabs left, we could exit or keep editor open
            if len(self.open_tabs) == 0:
                self.active_tab_index = 0

    def _python_syntax_highlight(self, line):
        """Apply Python syntax highlighting to a line"""
        # Simple keyword-based highlighting
        keywords = ['def', 'class', 'if', 'elif', 'else', 'for', 'while', 'try', 'except',
                   'finally', 'with', 'import', 'from', 'as', 'return', 'yield', 'pass',
                   'break', 'continue', 'and', 'or', 'not', 'in', 'is', 'None', 'True', 'False']
        # String delimiters
        string_chars = ['"', "'"]

        # Simple tokenization (very basic)
        tokens = []
        i = 0
        while i < len(line):
            # Check for comments first (highest priority)
            if line[i] == '#':
                tokens.append(('comment', line[i:]))
                break

            # Check for strings
            if line[i] in string_chars:
                quote_char = line[i]
                start = i
                i += 1
                # Find end of string (handle escaped quotes)
                while i < len(line):
                    if line[i] == quote_char and (i == 0 or line[i-1] != '\\'):
                        break
                    i += 1
                if i < len(line):
                    i += 1
                tokens.append(('string', line[start:i]))
                continue

            # Check for numbers (integers and floats)
            if line[i].isdigit():
                start = i
                i += 1
                # Check for decimal point and more digits (float)
                if i < len(line) and line[i] == '.':
                    i += 1
                    while i < len(line) and line[i].isdigit():
                        i += 1
                # Check for exponent notation (e.g., 1e5, 1.5e-3)
                if i < len(line) and line[i].lower() == 'e':
                    i += 1
                    if i < len(line) and (line[i] == '+' or line[i] == '-'):
                        i += 1
                    while i < len(line) and line[i].isdigit():
                        i += 1
                tokens.append(('number', line[start:i]))
                continue

            # Check for identifiers (potential keywords or function calls)
            if line[i].isalpha() or line[i] == '_':
                start = i
                i += 1
                while i < len(line) and (line[i].isalnum() or line[i] == '_'):
                    i += 1
                identifier = line[start:i]

                # Check if it's a keyword
                if identifier in keywords:
                    tokens.append(('keyword', identifier))
                else:
                    # Check if it's followed by '(' - function call
                    # Look ahead (skip whitespace)
                    j = i
                    while j < len(line) and line[j] in ' \t':
                        j += 1
                    if j < len(line) and line[j] == '(':
                        tokens.append(('function', identifier))
                        # Don't advance i, let the next iteration handle the '('
                        i = start + len(identifier)
                    else:
                        # Regular identifier
                        tokens.append(('normal', identifier))
                continue

            # Regular character
            tokens.append(('normal', line[i]))
            i += 1

        return tokens

    def handle_events(self, events):
        """Handle input events"""
        for event in events:
            if event.type == pygame.KEYDOWN:
                # ESC handling: close quick open modal if active, otherwise quit editor
                if event.key == pygame.K_ESCAPE:
                    if self.quick_open_active:
                        # Close quick open modal, return to editor
                        self.quick_open_active = False
                        self.quick_open_query = ""
                        self.quick_open_results = []
                        return
                    else:
                        # Quit editor
                        self._save_all_files()
                        self.game.change_state(self.previous_state, call_enter=False)
                        return

                # Route keyboard input based on focused area
                if self.terminal_open and self.focused_area == 'terminal':
                    self._handle_terminal_keydown(event)
                else:
                    self._handle_keydown(event)
            elif event.type == pygame.KEYUP:
                # Clear key repeat state when key is released
                if event.key in self.key_repeat_state:
                    del self.key_repeat_state[event.key]
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_mouse_click(event)
            elif event.type == pygame.MOUSEBUTTONUP:
                self._handle_mouse_release(event)
            elif event.type == pygame.MOUSEMOTION:
                self._handle_mouse_motion(event)
            elif event.type == pygame.MOUSEWHEEL:
                self._handle_mouse_wheel(event)

    def _handle_keydown(self, event):
        """Handle keyboard input"""
        # ESC is handled in handle_events before routing here

        # Cmd+P to toggle quick open
        if (event.mod & pygame.KMOD_GUI) and event.key == pygame.K_p:
            self._toggle_quick_open()
            return

        # If quick open is active, handle its input
        if self.quick_open_active:
            self._handle_quick_open_keydown(event)
            return

        # Ctrl+F or Cmd+F to toggle search
        if (event.mod & pygame.KMOD_CTRL or event.mod & pygame.KMOD_GUI) and event.key == pygame.K_f:
            self._toggle_search()
            return

        # If in search tab, handle search input
        if self.sidebar_tab == "search":
            self._handle_search_keydown(event)
            return

        # If no tabs open, ignore most keys
        if len(self.open_tabs) == 0:
            return

        filename, full_path = self.open_tabs[self.active_tab_index]
        lines = self.file_contents.get(full_path, [""])

        if not lines:
            lines = [""]

        # Check if Shift is held for selection
        is_selecting = event.mod & pygame.KMOD_SHIFT

        # Save current cursor position before moving (for selection start)
        prev_line = self.cursor_line
        prev_col = self.cursor_col

        # Navigation
        if event.key == pygame.K_UP:
            if self.cursor_line > 0:
                self.cursor_line -= 1
                self.cursor_col = min(self.cursor_col, len(lines[self.cursor_line]))
                # Auto-scroll
                if self.cursor_line < self.editor_scroll_y:
                    self.editor_scroll_y = self.cursor_line
            # Handle selection
            if is_selecting:
                if self.selection_start is None:
                    # Start new selection at previous position
                    self.selection_start = (prev_line, prev_col)
                self.selection_end = (self.cursor_line, self.cursor_col)
            else:
                self._clear_selection()
            # Track for key repeat
            self.key_repeat_state[pygame.K_UP] = (pygame.time.get_ticks(), 0)

        elif event.key == pygame.K_DOWN:
            if self.cursor_line < len(lines) - 1:
                self.cursor_line += 1
                self.cursor_col = min(self.cursor_col, len(lines[self.cursor_line]))
                # Auto-scroll
                editor_height = self.renderer.char_height - 3  # Leave room for tabs and status
                if self.cursor_line >= self.editor_scroll_y + editor_height:
                    self.editor_scroll_y = self.cursor_line - editor_height + 1
            # Handle selection
            if is_selecting:
                if self.selection_start is None:
                    # Start new selection at previous position
                    self.selection_start = (prev_line, prev_col)
                self.selection_end = (self.cursor_line, self.cursor_col)
            else:
                self._clear_selection()
            # Track for key repeat
            self.key_repeat_state[pygame.K_DOWN] = (pygame.time.get_ticks(), 0)

        elif event.key == pygame.K_LEFT:
            # Check for Cmd/Ctrl modifier (go to start of line)
            if event.mod & (pygame.KMOD_META | pygame.KMOD_CTRL):
                self.cursor_col = 0
            else:
                if self.cursor_col > 0:
                    self.cursor_col -= 1
            # Handle selection
            if is_selecting:
                if self.selection_start is None:
                    # Start new selection at previous position
                    self.selection_start = (prev_line, prev_col)
                self.selection_end = (self.cursor_line, self.cursor_col)
            else:
                self._clear_selection()
            # Track for key repeat
            self.key_repeat_state[pygame.K_LEFT] = (pygame.time.get_ticks(), 0)

        elif event.key == pygame.K_RIGHT:
            # Check for Cmd/Ctrl modifier (go to end of line)
            if event.mod & (pygame.KMOD_META | pygame.KMOD_CTRL):
                self.cursor_col = len(lines[self.cursor_line])
            else:
                if self.cursor_col < len(lines[self.cursor_line]):
                    self.cursor_col += 1
            # Handle selection
            if is_selecting:
                if self.selection_start is None:
                    # Start new selection at previous position
                    self.selection_start = (prev_line, prev_col)
                self.selection_end = (self.cursor_line, self.cursor_col)
            else:
                self._clear_selection()
            # Track for key repeat
            self.key_repeat_state[pygame.K_RIGHT] = (pygame.time.get_ticks(), 0)

        elif event.key == pygame.K_HOME:
            self.cursor_col = 0
            if event.mod & pygame.KMOD_SHIFT:
                self._extend_selection()
            else:
                self._clear_selection()

        elif event.key == pygame.K_END:
            self.cursor_col = len(lines[self.cursor_line])
            if event.mod & pygame.KMOD_SHIFT:
                self._extend_selection()
            else:
                self._clear_selection()

        elif event.key == pygame.K_PAGEUP:
            editor_height = self.renderer.char_height - 3
            self.cursor_line = max(0, self.cursor_line - editor_height)
            self.editor_scroll_y = max(0, self.editor_scroll_y - editor_height)
            self.cursor_col = min(self.cursor_col, len(lines[self.cursor_line]))

        elif event.key == pygame.K_PAGEDOWN:
            editor_height = self.renderer.char_height - 3
            self.cursor_line = min(len(lines) - 1, self.cursor_line + editor_height)
            self.editor_scroll_y = min(len(lines) - editor_height, self.editor_scroll_y + editor_height)
            self.cursor_col = min(self.cursor_col, len(lines[self.cursor_line]))

        # Tab navigation
        elif event.mod & pygame.KMOD_CTRL and event.key == pygame.K_TAB:
            # Next tab
            if len(self.open_tabs) > 1:
                self.active_tab_index = (self.active_tab_index + 1) % len(self.open_tabs)
                self.cursor_line = 0
                self.cursor_col = 0
                self.editor_scroll_y = 0

        elif event.mod & pygame.KMOD_CTRL and event.key == pygame.K_w:
            # Close current tab
            if len(self.open_tabs) > 0:
                self._close_tab(self.active_tab_index)

        # Copy/Paste
        elif event.mod & (pygame.KMOD_META | pygame.KMOD_CTRL) and event.key == pygame.K_c:
            # Copy selection or current line
            if len(self.open_tabs) > 0:
                filename, full_path = self.open_tabs[self.active_tab_index]
                lines = self.file_contents.get(full_path, [""])
                if lines:
                    if self._has_selection():
                        # Copy selected text
                        self.clipboard = self._get_selected_text(lines)
                        self._show_status("Copied selection")
                    elif 0 <= self.cursor_line < len(lines):
                        # Copy current line if no selection
                        self.clipboard = [lines[self.cursor_line]]
                        self._show_status("Copied line")

        elif event.mod & (pygame.KMOD_META | pygame.KMOD_CTRL) and event.key == pygame.K_v:
            # Paste clipboard (replaces selection if exists)
            if len(self.open_tabs) > 0 and self.clipboard:
                filename, full_path = self.open_tabs[self.active_tab_index]
                lines = self.file_contents.get(full_path, [""])
                if not lines:
                    lines = [""]

                # Delete selection if it exists
                if self._has_selection():
                    lines, new_line, new_col = self._delete_selection(lines)
                    self.cursor_line = new_line
                    self.cursor_col = new_col
                    self._clear_selection()

                # Insert clipboard lines at cursor
                for i, clip_line in enumerate(self.clipboard):
                    if i == 0:
                        # First line: insert at cursor position
                        current = lines[self.cursor_line]
                        lines[self.cursor_line] = current[:self.cursor_col] + clip_line + current[self.cursor_col:]
                        self.cursor_col += len(clip_line)
                    else:
                        # Additional lines: insert as new lines
                        lines.insert(self.cursor_line + i, clip_line)
                        self.cursor_line += 1

                self.file_contents[full_path] = lines
                # Auto-save
                self._save_file(full_path, lines)
                self._show_status("Pasted")

        # Editing
        elif event.key == pygame.K_RETURN:
            # Insert new line with auto-indentation
            current = lines[self.cursor_line]

            # Calculate indentation for new line based on original line
            indent = self._calculate_indent(current)

            # Check if original line (before splitting) ends with colon or opening bracket
            # This handles the case where we're pressing Enter in the middle of a line
            original_stripped = current.rstrip()
            if original_stripped and (original_stripped[-1] == ':' or original_stripped[-1] in '([{'):
                indent += 4  # Python standard is 4 spaces

            # Split the line
            lines[self.cursor_line] = current[:self.cursor_col]
            new_line_content = current[self.cursor_col:]

            # Apply indentation to new line
            new_line = ' ' * indent + new_line_content
            lines.insert(self.cursor_line + 1, new_line)
            self.cursor_line += 1
            self.cursor_col = indent
            self.file_contents[full_path] = lines
            # Auto-save
            self._save_file(full_path, lines)
            self._show_status(f"Saved: {filename}")

        elif event.key == pygame.K_BACKSPACE:
            # Delete selection or character
            if self._has_selection():
                lines, new_line, new_col = self._delete_selection(lines)
                self.cursor_line = new_line
                self.cursor_col = new_col
                self._clear_selection()
                self.file_contents[full_path] = lines
                # Auto-save
                self._save_file(full_path, lines)
                self._show_status(f"Saved: {filename}")
            elif self.cursor_col > 0:
                # Delete character
                line = lines[self.cursor_line]
                lines[self.cursor_line] = line[:self.cursor_col-1] + line[self.cursor_col:]
                self.cursor_col -= 1
                self.file_contents[full_path] = lines
                # Auto-save
                self._save_file(full_path, lines)
                self._show_status(f"Saved: {filename}")
            elif self.cursor_line > 0:
                # Join with previous line
                prev_line = lines[self.cursor_line - 1]
                current_line = lines[self.cursor_line]
                lines[self.cursor_line - 1] = prev_line + current_line
                del lines[self.cursor_line]
                self.cursor_line -= 1
                self.cursor_col = len(prev_line)
                self.file_contents[full_path] = lines
                # Auto-save
                self._save_file(full_path, lines)
                self._show_status(f"Saved: {filename}")

        elif event.key == pygame.K_DELETE:
            # Delete character after cursor
            line = lines[self.cursor_line]
            if self.cursor_col < len(line):
                lines[self.cursor_line] = line[:self.cursor_col] + line[self.cursor_col+1:]
                self.file_contents[full_path] = lines
                # Auto-save
                self._save_file(full_path, lines)
                self._show_status(f"Saved: {filename}")

        elif event.unicode and event.unicode.isprintable():
            # Insert character (replaces selection if exists)
            if self._has_selection():
                lines, new_line, new_col = self._delete_selection(lines)
                self.cursor_line = new_line
                self.cursor_col = new_col
                self._clear_selection()

            # Insert character
            line = lines[self.cursor_line]
            lines[self.cursor_line] = line[:self.cursor_col] + event.unicode + line[self.cursor_col:]
            self.cursor_col += 1
            self.file_contents[full_path] = lines
            # Auto-save
            self._save_file(full_path, lines)
            self._show_status(f"Saved: {filename}")

    def _calculate_indent(self, line):
        """Calculate the indentation level (number of leading spaces) of a line"""
        indent = 0
        for char in line:
            if char == ' ':
                indent += 1
            elif char == '\t':
                indent += 4  # Treat tabs as 4 spaces
            else:
                break
        return indent

    def _has_selection(self):
        """Check if there is an active selection"""
        return self.selection_start is not None and self.selection_end is not None

    def _clear_selection(self):
        """Clear the current selection"""
        self.selection_start = None
        self.selection_end = None

    def _extend_selection(self):
        """Extend or start selection from current cursor position"""
        if self.selection_start is None:
            # Start new selection
            self.selection_start = (self.cursor_line, self.cursor_col)
        # Update end of selection
        self.selection_end = (self.cursor_line, self.cursor_col)

    def _normalize_selection(self):
        """Ensure selection_start comes before selection_end"""
        if not self._has_selection():
            return

        start_line, start_col = self.selection_start
        end_line, end_col = self.selection_end

        # Swap if end comes before start
        if end_line < start_line or (end_line == start_line and end_col < start_col):
            self.selection_start, self.selection_end = self.selection_end, self.selection_start

    def _get_selected_text(self, lines):
        """Get the selected text as a list of lines"""
        if not self._has_selection():
            return []

        self._normalize_selection()
        start_line, start_col = self.selection_start
        end_line, end_col = self.selection_end

        selected_lines = []

        if start_line == end_line:
            # Single line selection
            line = lines[start_line]
            selected_lines.append(line[start_col:end_col])
        else:
            # Multi-line selection
            # First line: from start_col to end
            first_line = lines[start_line]
            selected_lines.append(first_line[start_col:])

            # Middle lines: entire lines
            for line_num in range(start_line + 1, end_line):
                selected_lines.append(lines[line_num])

            # Last line: from start to end_col
            last_line = lines[end_line]
            selected_lines.append(last_line[:end_col])

        return selected_lines

    def _delete_selection(self, lines):
        """Delete the selected text and return (new_lines, new_line, new_col)"""
        if not self._has_selection():
            return lines, self.cursor_line, self.cursor_col

        self._normalize_selection()
        start_line, start_col = self.selection_start
        end_line, end_col = self.selection_end

        if start_line == end_line:
            # Single line selection
            line = lines[start_line]
            lines[start_line] = line[:start_col] + line[end_col:]
            return lines, start_line, start_col
        else:
            # Multi-line selection
            # Merge first and last lines
            first_line = lines[start_line]
            last_line = lines[end_line]
            lines[start_line] = first_line[:start_col] + last_line[end_col:]

            # Delete middle lines (in reverse to maintain indices)
            for line_num in range(end_line, start_line, -1):
                del lines[line_num]

            return lines, start_line, start_col

    def _handle_mouse_click(self, event):
        """Handle mouse clicks"""
        if event.button == 1:  # Left click
            # Account for title bar height
            title_bar_pixels = self.renderer.title_bar_height
            adjusted_y = event.pos[1] - title_bar_pixels

            # Only process clicks in the character grid area
            if adjusted_y < 0:
                return

            mouse_x = event.pos[0] // self.renderer.cell_width
            mouse_y = adjusted_y // self.renderer.cell_height

            # Check if quick open modal is active - handle clicks on it first
            if self.quick_open_active:
                self._handle_quick_open_click(mouse_x, mouse_y)
                return

            # Check if clicking on sidebar drag handle (within 1 character width)
            if abs(mouse_x - self.sidebar_width) <= 1:
                self.sidebar_drag_x = event.pos[0]

            # Check if clicking in sidebar
            elif mouse_x < self.sidebar_width:
                self._handle_sidebar_click(mouse_x, mouse_y)

            # Check if clicking on tabs
            elif mouse_x > self.sidebar_width + 1 and mouse_y < 2:
                self._handle_tab_click(mouse_x, mouse_y)

            # Check if clicking on terminal divider (if terminal is open)
            elif self.terminal_open and self._is_terminal_divider_y(mouse_y):
                self.terminal_drag_y = event.pos[1]

            # Check if clicking in terminal area
            elif self.terminal_open and self._is_in_terminal_area(mouse_x, mouse_y):
                # Set focus to terminal
                self.focused_area = 'terminal'

            # Check if clicking in editor area (below tabs, above terminal)
            elif mouse_x > self.sidebar_width + 1 and mouse_y >= 2:
                if not self.terminal_open or mouse_y < self.renderer.char_height - self.terminal_height - 1:
                    # Set focus to editor
                    self.focused_area = 'editor'
                    self._handle_editor_click(mouse_x, mouse_y)

    def _handle_sidebar_click(self, mouse_x, mouse_y):
        """Handle clicks in the sidebar"""
        # Check if clicking on "Toggle Terminal" button (row 0)
        if mouse_y == 0:
            self.terminal_open = not self.terminal_open
            if not self.terminal_open:
                # Clear terminal input when closing
                self.terminal_input_buffer = ""
                self.focused_area = 'editor'  # Return focus to editor
            else:
                # When opening terminal, focus it
                self.focused_area = 'terminal'
            return

        # Check if clicking on tabs (row 2): "Files | Search"
        if mouse_y == 2:
            # "Files" is at x=0-4, "Search" is at x=7-12
            if mouse_x < 6:
                # Clicked on "Files" tab
                self.sidebar_tab = "files"
            else:
                # Clicked on "Search" tab
                self.sidebar_tab = "search"
            return

        # Route click to appropriate tab content
        self.focused_area = 'editor'  # Clicks in sidebar focus editor

        if self.sidebar_tab == "search":
            self._handle_search_tab_click(mouse_y)
        else:
            self._handle_files_tab_click(mouse_y)

    def _handle_files_tab_click(self, mouse_y):
        """Handle clicks in the Files tab"""
        # Account for: terminal button (row 0), separator (row 1), tabs (row 2)
        # So actual tree starts at row 3
        click_y = mouse_y - 3

        tree = self._get_file_tree()
        if 0 <= click_y < len(tree):
            item = tree[click_y]
            if item['type'] == 'dir':
                # Toggle expansion
                if item['expanded']:
                    self.expanded_dirs.discard(item['path'])
                else:
                    self.expanded_dirs.add(item['path'])
            elif item['type'] == 'file':
                # Open file
                self._open_file(item['path'], item['name'])
                self.selected_file = item['path']

    def _handle_search_tab_click(self, mouse_y):
        """Handle clicks in the Search tab"""
        # Account for: terminal button (row 0), separator (row 1), tabs (row 2), search input (row 3)
        # So search results start at row 4
        click_y = mouse_y - 4

        if click_y < 0 or click_y >= len(self.search_results):
            return

        try:
            result = self.search_results[click_y]

            if result[0] == 'file':
                # Clicked on file header - open file at first match
                filepath = result[1]
                filename = filepath.split('/')[-1]
                self._open_file(filepath, filename)
                # Find first match for this file and navigate to it
                for r in self.search_results:
                    if r[0] == 'match' and r[1] == filepath:
                        line_num = r[2]
                        self.cursor_line = line_num
                        self.editor_scroll_y = max(0, line_num - 5)
                        break
                self.sidebar_tab = "files"
            elif result[0] == 'match':
                # Clicked on match line - open file and navigate to that line
                filepath, line_num = result[1], result[2]
                filename = filepath.split('/')[-1]
                self._open_file(filepath, filename)
                # Navigate to the matching line (after _open_file resets cursor)
                self.cursor_line = line_num
                self.editor_scroll_y = max(0, line_num - 5)  # Scroll to show line with some context
                # Also switch back to files tab to see the opened file
                self.sidebar_tab = "files"
        except Exception:
            # If file can't be opened, don't crash - just ignore
            pass

    def _handle_tab_click(self, mouse_x, mouse_y):
        """Handle clicks on tabs"""
        # Calculate which tab was clicked
        editor_start_x = self.sidebar_width + 2
        tab_start_x = editor_start_x

        for i, (filename, _) in enumerate(self.open_tabs):
            # Tab text is " {filename} [X] " = 1 space + filename + 1 space + "[X]" + 1 space
            tab_text = f" {filename} [X] "
            tab_width = len(tab_text)

            if tab_start_x <= mouse_x < tab_start_x + tab_width:
                # Close button "[X]" starts after: 1 space + filename + 1 space
                # So it starts at tab_start_x + len(filename) + 2
                # Make the close button area a bit larger for easier clicking
                close_button_start = tab_start_x + len(filename) + 2
                close_button_end = tab_start_x + tab_width - 1  # Leave last space for tab switching

                # Check if clicking close button (with some margin for easier clicking)
                if mouse_x >= close_button_start - 1 and mouse_x <= close_button_end:
                    self._close_tab(i)
                else:
                    # Clicking on tab name - switch to this tab
                    self.active_tab_index = i
                    # Reset editor state for this tab
                    self.cursor_line = 0
                    self.cursor_col = 0
                    self.editor_scroll_y = 0
                return
            tab_start_x += tab_width + 1

    def _handle_editor_click(self, mouse_x, mouse_y):
        """Handle clicks in the editor area to move cursor"""
        if len(self.open_tabs) == 0:
            return

        filename, full_path = self.open_tabs[self.active_tab_index]
        lines = self.file_contents.get(full_path, [""])

        if not lines:
            lines = [""]

        editor_start_x = self.sidebar_width + 2

        # Calculate which line was clicked
        # Tabs are on row 0-1, editor starts at row 2
        editor_row = mouse_y - 2  # Subtract 2 for tabs

        if editor_row < 0:
            return

        # Calculate the actual line number in the file
        clicked_line = self.editor_scroll_y + editor_row

        if clicked_line < 0 or clicked_line >= len(lines):
            # Clicked beyond file bounds - move to end of file
            self.cursor_line = len(lines) - 1
            self.cursor_col = len(lines[self.cursor_line])
        else:
            self.cursor_line = clicked_line

            # Calculate which column was clicked
            # Need to account for line numbers
            line_num_width = len(str(len(lines))) + 1
            line_start_x = editor_start_x + line_num_width + 1

            # Calculate column based on mouse position
            if mouse_x < line_start_x:
                # Clicked on line number area - move to start of line
                self.cursor_col = 0
            else:
                # Calculate column position
                col_offset = mouse_x - line_start_x
                line = lines[self.cursor_line]
                # Clamp to line length
                self.cursor_col = min(col_offset, len(line))

        # Clear selection when clicking
        self._clear_selection()

        # Auto-scroll to keep cursor visible if needed
        editor_height = self.renderer.char_height - 3
        if self.cursor_line < self.editor_scroll_y:
            self.editor_scroll_y = self.cursor_line
        elif self.cursor_line >= self.editor_scroll_y + editor_height:
            self.editor_scroll_y = self.cursor_line - editor_height + 1

    def _handle_mouse_release(self, event):
        """Handle mouse release"""
        if event.button == 1:
            self.sidebar_drag_x = None
            self.terminal_drag_y = None

    def _handle_mouse_motion(self, event):
        """Handle mouse motion (for dragging sidebar and terminal divider)"""
        if self.sidebar_drag_x is not None and event.buttons[0]:  # Left button held
            # Calculate new sidebar width
            new_width_chars = event.pos[0] // self.renderer.cell_width
            new_width_chars = max(self.sidebar_min_width, min(self.sidebar_max_width, new_width_chars))
            self.sidebar_width = new_width_chars
        elif self.terminal_drag_y is not None and event.buttons[0]:  # Dragging terminal divider
            # Calculate new terminal height
            title_bar_pixels = self.renderer.title_bar_height
            adjusted_y = event.pos[1] - title_bar_pixels
            mouse_y = adjusted_y // self.renderer.cell_height
            # Terminal divider is at: char_height - terminal_height - 1
            # So terminal_height = char_height - mouse_y - 1
            new_height = self.renderer.char_height - mouse_y - 1
            new_height = max(self.terminal_min_height, min(self.terminal_max_height, new_height))
            self.terminal_height = new_height

    def _handle_mouse_wheel(self, event):
        """Handle mouse wheel scrolling"""
        # Check if scrolling in terminal area (and terminal is focused)
        if self.terminal_open and self.focused_area == 'terminal':
            # Scroll terminal output
            scroll_amount = -event.y * 3
            max_scroll = max(0, len(self.terminal_output_lines) - (self.terminal_height - 1))
            self.terminal_scroll_offset = max(0, min(max_scroll, self.terminal_scroll_offset + scroll_amount))
            return

        if len(self.open_tabs) == 0:
            return

        # Scroll editor
        scroll_amount = -event.y * 3  # Scroll 3 lines per wheel click
        self.editor_scroll_y = max(0, min(
            len(self.file_contents.get(self.open_tabs[self.active_tab_index][1], [""])) - 1,
            self.editor_scroll_y + scroll_amount
        ))

    def _show_status(self, message):
        """Show a status message"""
        self.status_message = message
        self.status_message_timeout = 120  # Show for 2 seconds at 60fps

    def update(self, dt):
        """Update editor state"""
        # Update status message timeout
        if self.status_message_timeout > 0:
            self.status_message_timeout -= 1
            if self.status_message_timeout == 0:
                self.status_message = "Code Editor | ESC to quit | Click files to open"

        # Update terminal cursor blink (only if terminal is focused)
        if self.terminal_open and self.focused_area == 'terminal':
            self.terminal_cursor_timer += dt
            if self.terminal_cursor_timer >= 500:  # Blink every 500ms
                self.terminal_cursor_visible = not self.terminal_cursor_visible
                self.terminal_cursor_timer = 0
        elif self.terminal_open:
            # Reset cursor visibility when not focused
            self.terminal_cursor_visible = True
            self.terminal_cursor_timer = 0

        # Handle key repeat for arrow keys
        if len(self.open_tabs) > 0:
            filename, full_path = self.open_tabs[self.active_tab_index]
            lines = self.file_contents.get(full_path, [""])
            if not lines:
                lines = [""]

            current_time = pygame.time.get_ticks()
            keys_to_remove = []

            for key, (press_time, repeat_count) in list(self.key_repeat_state.items()):
                # Check if key is still held down
                keys = pygame.key.get_pressed()
                if not keys[key]:
                    keys_to_remove.append(key)
                    continue

                # Calculate time since last action
                if repeat_count == 0:
                    # First repeat - use longer delay
                    delay = self.key_repeat_delay
                else:
                    # Subsequent repeats - use shorter interval
                    delay = self.key_repeat_interval

                if current_time - press_time >= delay:
                    # Check if Shift is held for selection
                    keys = pygame.key.get_pressed()
                    is_selecting = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]

                    # Save previous position for selection
                    prev_line = self.cursor_line
                    prev_col = self.cursor_col

                    # Time to repeat
                    if key == pygame.K_LEFT:
                        if self.cursor_col > 0:
                            self.cursor_col -= 1
                    elif key == pygame.K_RIGHT:
                        if self.cursor_col < len(lines[self.cursor_line]):
                            self.cursor_col += 1
                    elif key == pygame.K_UP:
                        if self.cursor_line > 0:
                            self.cursor_line -= 1
                            self.cursor_col = min(self.cursor_col, len(lines[self.cursor_line]))
                            if self.cursor_line < self.editor_scroll_y:
                                self.editor_scroll_y = self.cursor_line
                    elif key == pygame.K_DOWN:
                        if self.cursor_line < len(lines) - 1:
                            self.cursor_line += 1
                            self.cursor_col = min(self.cursor_col, len(lines[self.cursor_line]))
                            editor_height = self.renderer.char_height - 3
                            if self.cursor_line >= self.editor_scroll_y + editor_height:
                                self.editor_scroll_y = self.cursor_line - editor_height + 1

                    # Handle selection
                    if is_selecting:
                        if self.selection_start is None:
                            # Start new selection at previous position
                            self.selection_start = (prev_line, prev_col)
                        self.selection_end = (self.cursor_line, self.cursor_col)
                    else:
                        self._clear_selection()

                    # Update repeat state
                    self.key_repeat_state[key] = (current_time, repeat_count + 1)

            # Remove keys that are no longer pressed
            for key in keys_to_remove:
                del self.key_repeat_state[key]

    def render(self):
        """Render the editor"""
        self.renderer.clear()

        # Draw sidebar
        self._render_sidebar()

        # Draw divider
        divider_x = self.sidebar_width
        for y in range(self.renderer.char_height):
            self.renderer.write(divider_x, y, "|", (150, 150, 150))

        # Draw editor area
        self._render_editor()

        # Draw terminal if open
        if self.terminal_open:
            self._render_terminal()

        # Draw status bar
        self._render_status_bar()

        # Draw quick open modal if active (on top of everything)
        if self.quick_open_active:
            self._render_quick_open()

        self.renderer.render()

    def _render_sidebar(self):
        """Render the file tree sidebar with tabs for Files and Search"""
        # Toggle Terminal button (row 0)
        terminal_text = "Close Terminal" if self.terminal_open else "Open Terminal"
        terminal_color = (100, 255, 100) if self.terminal_open else (150, 150, 150)
        self.renderer.write(0, 0, terminal_text[:self.sidebar_width], terminal_color)

        # Separator line (row 1)
        separator = "-" * self.sidebar_width
        self.renderer.write(0, 1, separator, (100, 100, 100))

        # Sidebar tabs (row 2): Files | Search
        files_color = (255, 255, 255) if self.sidebar_tab == "files" else (100, 100, 100)
        search_color = (255, 255, 255) if self.sidebar_tab == "search" else (100, 100, 100)

        # Draw full tabs line first with neutral color
        tabs_text = "Files | Search"
        self.renderer.write(0, 2, tabs_text[:self.sidebar_width], (150, 150, 150))

        # Highlight the active tab by coloring
        if self.sidebar_tab == "files":
            # Color "Files" (positions 0-4)
            for i, char in enumerate("Files"):
                self.renderer.write(i, 2, char, files_color)
        else:
            # Color "Search" (positions 8-13)
            for i, char in enumerate("Search"):
                self.renderer.write(8 + i, 2, char, search_color)

        # Render content based on active tab
        if self.sidebar_tab == "search":
            self._render_search_tab()
        else:
            self._render_files_tab()

    def _render_files_tab(self):
        """Render the Files tab content"""
        # Get file tree
        tree = self._get_file_tree()

        # Render tree items (starting at row 3, immediately after tabs)
        start_y = 3
        for i, item in enumerate(tree):
            y = start_y + i
            if y >= self.renderer.char_height - 1:
                break

            # Highlight selected file
            color = (255, 255, 255) if item.get('path') == self.selected_file else (150, 150, 150)

            # Truncate display text to fit sidebar
            display_text = item['display']
            if len(display_text) > self.sidebar_width:
                display_text = display_text[:self.sidebar_width-1] + "…"

            self.renderer.write(0, y, display_text, color)

    def _render_search_tab(self):
        """Render the Search tab content - search within files"""
        # Search input box (row 3)
        search_text = self.search_query
        if len(search_text) > self.sidebar_width - 2:
            search_text = search_text[:self.sidebar_width - 3] + ">"
        search_text = ("🔍 " + search_text).ljust(self.sidebar_width)
        self.renderer.write(0, 3, search_text, (200, 200, 100))

        # Show search results grouped by file
        if self.search_query.strip():
            start_y = 4
            current_y = start_y

            for i, result in enumerate(self.search_results):
                if current_y >= self.renderer.char_height - 1:
                    break

                if result[0] == 'file':
                    # File header
                    filepath = result[1]
                    color = (0, 255, 100) if i == self.search_cursor else (200, 200, 200)
                    display_text = filepath
                    if len(display_text) > self.sidebar_width:
                        display_text = display_text[:self.sidebar_width - 1] + "…"
                    self.renderer.write(0, current_y, display_text, color)
                    current_y += 1
                elif result[0] == 'match':
                    # Match line (indented)
                    line_text = result[3]
                    color = (0, 255, 100) if i == self.search_cursor else (150, 150, 150)
                    # Indent with 4 spaces
                    display_text = "    " + line_text
                    if len(display_text) > self.sidebar_width:
                        display_text = display_text[:self.sidebar_width - 1] + "…"
                    self.renderer.write(0, current_y, display_text, color)
                    current_y += 1
        else:
            # Show hint when no search query
            hint = "Type to search..."
            self.renderer.write(0, 4, hint, (100, 100, 100))

    def _render_quick_open(self):
        """Render the quick open modal dialog"""
        # Calculate modal size (centered, taking up middle portion of screen)
        modal_width = min(60, self.renderer.char_width - 10)
        modal_height = min(20, self.renderer.char_height - 6)
        modal_start_x = (self.renderer.char_width - modal_width) // 2
        modal_start_y = (self.renderer.char_height - modal_height) // 2

        # Draw opaque dark background overlay (entire screen)
        for y in range(self.renderer.char_height):
            for x in range(self.renderer.char_width):
                # If outside modal, darken completely
                if not (modal_start_y <= y < modal_start_y + modal_height and \
                        modal_start_x <= x < modal_start_x + modal_width):
                    self.renderer.write(x, y, " ", (20, 20, 20))
                else:
                    # Inside modal, fill with dark background
                    self.renderer.write(x, y, " ", (40, 40, 40))

        # Draw modal box border
        for x in range(modal_start_x, modal_start_x + modal_width):
            self.renderer.write(x, modal_start_y, "─", (200, 200, 200))
            self.renderer.write(x, modal_start_y + modal_height - 1, "─", (200, 200, 200))

        for y in range(modal_start_y, modal_start_y + modal_height):
            self.renderer.write(modal_start_x, y, "│", (200, 200, 200))
            self.renderer.write(modal_start_x + modal_width - 1, y, "│", (200, 200, 200))

        # Draw search input (row 1 of modal)
        search_text = self.quick_open_query
        if len(search_text) > modal_width - 4:
            search_text = search_text[:modal_width - 5] + ">"
        search_prompt = "❯ " + search_text
        search_prompt = search_prompt.ljust(modal_width - 2)
        self.renderer.write(modal_start_x + 1, modal_start_y + 1, search_prompt[:modal_width - 2], (200, 200, 100))

        # Draw results (starting from row 2 of modal)
        result_start_y = modal_start_y + 2
        max_results = modal_height - 3

        for i, filepath in enumerate(self.quick_open_results[:max_results]):
            y = result_start_y + i

            # Highlight selected result
            color = (0, 255, 100) if i == self.quick_open_cursor else (150, 150, 150)

            # Show filename with path hint
            display_text = filepath
            if len(display_text) > modal_width - 4:
                display_text = display_text[:modal_width - 5] + "…"

            self.renderer.write(modal_start_x + 1, y, display_text, color)

        # Show hint if no results
        if not self.quick_open_results and self.quick_open_query.strip():
            hint = "No files found"
            self.renderer.write(modal_start_x + 1, result_start_y, hint, (100, 100, 100))

    def _render_editor(self):
        """Render the editor pane"""
        editor_start_x = self.sidebar_width + 2

        # Calculate editor height (account for terminal if open)
        status_bar_height = 1
        tab_height = 1
        terminal_height = self.terminal_height if self.terminal_open else 0
        editor_height = self.renderer.char_height - status_bar_height - tab_height - terminal_height

        # Draw tabs
        self._render_tabs(editor_start_x)

        # Draw editor content
        if len(self.open_tabs) > 0:
            filename, full_path = self.open_tabs[self.active_tab_index]
            lines = self.file_contents.get(full_path, [""])

            if not lines:
                lines = [""]

            # Calculate visible area
            start_line = self.editor_scroll_y
            end_line = min(len(lines), start_line + editor_height)

            # Draw lines with line numbers
            line_num_width = len(str(len(lines))) + 1  # Width for line numbers

            for i in range(start_line, end_line):
                y = 2 + (i - start_line)  # Start after tabs
                line_num = str(i + 1)

                # Line number
                self.renderer.write(editor_start_x, y, line_num.rjust(line_num_width), (100, 100, 100))

                # Line content with syntax highlighting
                line = lines[i]
                line_start_x = editor_start_x + line_num_width + 1

                # Check if there's a selection on this line
                is_selected = False
                sel_start_col = -1
                sel_end_col = -1
                if self._has_selection():
                    self._normalize_selection()
                    start_line, start_col = self.selection_start
                    end_line, end_col = self.selection_end

                    if start_line <= i <= end_line:
                        is_selected = True
                        if start_line == end_line:
                            # Single line selection
                            sel_start_col = start_col
                            sel_end_col = end_col
                        elif i == start_line:
                            # First line of multi-line selection
                            sel_start_col = start_col
                            sel_end_col = len(line)
                        elif i == end_line:
                            # Last line of multi-line selection
                            sel_start_col = 0
                            sel_end_col = end_col
                        else:
                            # Middle line of multi-line selection
                            sel_start_col = 0
                            sel_end_col = len(line)

                # Check if it's a Python file
                is_python = filename.endswith('.py')

                if is_python:
                    # Apply syntax highlighting
                    tokens = self._python_syntax_highlight(line)
                    x_offset = 0
                    for token_type, token_text in tokens:
                        # Determine base color for this token
                        if token_type == 'keyword':
                            base_color = (100, 200, 255)  # Light blue
                        elif token_type == 'string':
                            base_color = (200, 255, 100)  # Light green
                        elif token_type == 'comment':
                            base_color = (150, 150, 150)  # Gray
                        elif token_type == 'function':
                            base_color = (255, 200, 100)  # Orange/yellow for function calls
                        elif token_type == 'number':
                            base_color = (150, 200, 255)  # Light blue for numbers
                        else:
                            base_color = (255, 255, 255)  # White

                        # Write token
                        for char in token_text:
                            if line_start_x + x_offset < self.renderer.char_width:
                                # Check if this character is selected
                                if is_selected and sel_start_col <= x_offset < sel_end_col:
                                    # Use bright cyan for selected text
                                    color = (0, 255, 255)  # Bright cyan
                                else:
                                    color = base_color

                                # Handle special characters that might break rendering
                                try:
                                    self.renderer.write(line_start_x + x_offset, y, char, color)
                                except (pygame.error, UnicodeError):
                                    self.renderer.write(line_start_x + x_offset, y, "?", color)
                                x_offset += 1
                else:
                    # No syntax highlighting
                    max_width = self.renderer.char_width - line_start_x
                    for col in range(min(max_width, len(line))):
                        char = line[col]
                        # Check if this character is selected
                        if is_selected and sel_start_col <= col < sel_end_col:
                            color = (0, 255, 255)  # Bright cyan for selection
                        else:
                            color = (255, 255, 255)  # White
                        self.renderer.write(line_start_x + col, y, char, color)

                # Show cursor on current line (only if editor is focused)
                if i == self.cursor_line and self.focused_area == 'editor':
                    cursor_x = line_start_x + self.cursor_col
                    if cursor_x < self.renderer.char_width:
                        # Show cursor as block
                        # Draw cursor by overwriting the character
                        if self.cursor_col < len(line):
                            # Save original char and color, then draw cursor
                            self.renderer.write(cursor_x, y, "█", (255, 255, 0))
                        else:
                            # At end of line
                            self.renderer.write(cursor_x, y, "█", (255, 255, 0))
        else:
            # No files open - show welcome message
            welcome_y = self.renderer.char_height // 2
            welcome_text = "No files open. Click a file in the sidebar to open it."
            self.renderer.write(editor_start_x, welcome_y, welcome_text, (150, 150, 150))

    def _render_tabs(self, start_x):
        """Render the tab bar"""
        y = 0

        for i, (filename, _full_path) in enumerate(self.open_tabs):
            is_active = (i == self.active_tab_index)

            # Tab background
            if i == 0:
                tab_text = f" {filename} [X] "
            else:
                tab_text = f"/ {filename} [X] "
            tab_color = (200, 200, 200) if is_active else (100, 100, 100)

            # Draw tab
            x = start_x
            for char in tab_text:
                if x < self.renderer.char_width:
                    self.renderer.write(x, y, char, tab_color)
                    x += 1

            start_x = x + 1

    def _render_terminal(self):
        """Render the terminal pane at the bottom"""
        editor_start_x = self.sidebar_width + 2
        terminal_start_y = self.renderer.char_height - self.terminal_height - 1  # -1 for status bar

        # Clear entire terminal area with background first
        terminal_bg_color = (20, 20, 20)  # Dark background
        for y in range(terminal_start_y, self.renderer.char_height - 1):  # -1 for status bar
            for x in range(editor_start_x, self.renderer.char_width):
                self.renderer.write(x, y, " ", terminal_bg_color)

        # Draw terminal divider (resizable handle)
        divider_y = terminal_start_y - 1
        # Highlight divider if terminal is focused
        if self.focused_area == 'terminal':
            divider_color = (100, 255, 100) if self.terminal_drag_y is not None else (150, 255, 150)
        else:
            divider_color = (100, 200, 255) if self.terminal_drag_y is not None else (100, 100, 100)
        for x in range(editor_start_x, self.renderer.char_width):
            self.renderer.write(x, divider_y, "=", divider_color)
        # Draw handle indicator
        handle_text = "+++"
        handle_x = editor_start_x + (self.renderer.char_width - editor_start_x - len(handle_text)) // 2
        self.renderer.write(handle_x, divider_y, handle_text, divider_color)

        # Calculate visible terminal area
        visible_lines = self.terminal_height - 1  # -1 for input line
        max_scroll = max(0, len(self.terminal_output_lines) - visible_lines)
        self.terminal_scroll_offset = min(self.terminal_scroll_offset, max_scroll)

        if len(self.terminal_output_lines) <= visible_lines:
            start_idx = 0
        else:
            start_idx = max(0, len(self.terminal_output_lines) - visible_lines - self.terminal_scroll_offset)

        visible_output = self.terminal_output_lines[start_idx:start_idx + visible_lines]

        # Draw terminal output
        for i, line in enumerate(visible_output):
            y = terminal_start_y + i
            if y < self.renderer.char_height - 1:  # Don't draw over status bar
                # Truncate line to fit
                max_width = self.renderer.char_width - editor_start_x
                display_line = line[:max_width] if len(line) <= max_width else line[:max_width-1] + "…"
                self.renderer.write(editor_start_x, y, display_line, (200, 200, 200))

        # Draw input line at bottom of terminal
        input_y = self.renderer.char_height - 2  # -2 for status bar
        prompt = self._get_terminal_prompt()
        shell = getattr(self.previous_state, "shell", None)
        secret = bool(shell and shell.session and shell.session.secret)
        typed = "*" * len(self.terminal_input_buffer) if secret else self.terminal_input_buffer
        input_text = prompt + typed
        max_width = self.renderer.char_width - editor_start_x
        if len(input_text) > max_width:
            # Show end of input with ellipsis
            display_text = "…" + input_text[-(max_width-1):]
        else:
            display_text = input_text
        # Highlight input line if terminal is focused
        input_color = (255, 255, 255) if self.focused_area == 'terminal' else (150, 150, 150)
        self.renderer.write(editor_start_x, input_y, display_text, input_color)

        # Draw cursor (only if terminal is focused)
        if self.focused_area == 'terminal' and self.terminal_cursor_visible:
            cursor_x = editor_start_x + len(prompt) + len(self.terminal_input_buffer)
            if cursor_x < self.renderer.char_width:
                self.renderer.write(cursor_x, input_y, "█", (255, 255, 0))

    def _get_terminal_prompt(self):
        """Get the terminal prompt (same as main menu)"""
        if hasattr(self.previous_state, 'get_prompt'):
            return self.previous_state.get_prompt()
        # Fallback prompt
        pwd = self.filesystem.get_pwd()
        user = self.filesystem.current_user
        return f"{user}@{pwd}$ "

    def _render_status_bar(self):
        """Render the status bar"""
        status_y = self.renderer.char_height - 1

        # Status message
        status_text = self.status_message[:self.renderer.char_width]
        self.renderer.write(0, status_y, status_text, (200, 200, 200))

        # File info (if tab is open)
        if len(self.open_tabs) > 0:
            filename, full_path = self.open_tabs[self.active_tab_index]
            lines = self.file_contents.get(full_path, [""])
            file_info = f"{filename} | {len(lines)} lines | Line {self.cursor_line + 1}, Col {self.cursor_col + 1}"
            info_x = self.renderer.char_width - len(file_info)
            if info_x > len(status_text):
                self.renderer.write(info_x, status_y, file_info, (150, 150, 150))

    def _is_terminal_focused(self):
        """Check if terminal is currently focused (for input)"""
        return self.terminal_open and self.focused_area == 'terminal'

    def _is_terminal_divider_y(self, mouse_y):
        """Check if mouse_y is on the terminal divider"""
        divider_y = self.renderer.char_height - self.terminal_height - 1
        return abs(mouse_y - divider_y) <= 1

    def _is_in_terminal_area(self, mouse_x, mouse_y):
        """Check if mouse is in terminal area"""
        terminal_start_y = self.renderer.char_height - self.terminal_height - 1
        return mouse_y >= terminal_start_y and mouse_x > self.sidebar_width + 1


    def _handle_search_keydown(self, event):
        """Handle keyboard input for sidebar content search"""
        if event.key == pygame.K_BACKSPACE:
            # Remove last character from search
            if self.search_query:
                self.search_query = self.search_query[:-1]
                self._search_file_content(self.search_query)
            return

        if event.key == pygame.K_UP:
            # Navigate search results up
            if self.search_results:
                self.search_cursor = max(0, self.search_cursor - 1)
            return

        if event.key == pygame.K_DOWN:
            # Navigate search results down
            if self.search_results:
                self.search_cursor = min(len(self.search_results) - 1, self.search_cursor + 1)
            return

        if event.key == pygame.K_RETURN:
            # Open file at selected search result
            if self.search_results and 0 <= self.search_cursor < len(self.search_results):
                result = self.search_results[self.search_cursor]

                if result[0] == 'file':
                    # Open file at first match
                    filepath = result[1]
                    filename = filepath.split('/')[-1]
                    self._open_file(filepath, filename)
                    # Find first match for this file
                    for r in self.search_results:
                        if r[0] == 'match' and r[1] == filepath:
                            line_num = r[2]
                            self.cursor_line = line_num
                            self.editor_scroll_y = max(0, line_num - 5)
                            break
                    self.sidebar_tab = "files"
                elif result[0] == 'match':
                    # Open file at specific match line
                    filepath, line_num, _ = result[1], result[2], result[3]
                    filename = filepath.split('/')[-1]
                    self._open_file(filepath, filename)
                    self.cursor_line = line_num
                    self.editor_scroll_y = max(0, line_num - 5)
                    self.sidebar_tab = "files"
            return

        if event.unicode and event.unicode.isprintable():
            # Add character to search query
            self.search_query += event.unicode
            self._search_file_content(self.search_query)

    def _handle_quick_open_keydown(self, event):
        """Handle keyboard input for quick open dialog"""
        if event.key == pygame.K_ESCAPE:
            # Close quick open
            self.quick_open_active = False
            self.quick_open_query = ""
            self.quick_open_results = []
            return

        if event.key == pygame.K_BACKSPACE:
            # Remove last character from search
            if self.quick_open_query:
                self.quick_open_query = self.quick_open_query[:-1]
                self._search_files_quick_open(self.quick_open_query)
            return

        if event.key == pygame.K_UP:
            # Navigate results up
            if self.quick_open_results:
                self.quick_open_cursor = max(0, self.quick_open_cursor - 1)
            return

        if event.key == pygame.K_DOWN:
            # Navigate results down
            if self.quick_open_results:
                self.quick_open_cursor = min(len(self.quick_open_results) - 1, self.quick_open_cursor + 1)
            return

        if event.key == pygame.K_RETURN:
            # Open selected file
            if self.quick_open_results and 0 <= self.quick_open_cursor < len(self.quick_open_results):
                filepath = self.quick_open_results[self.quick_open_cursor]
                # Skip directories
                if not filepath.endswith('/'):
                    filename = filepath.split('/')[-1]
                    self._open_file(filepath, filename)
                    self.quick_open_active = False
                    self.quick_open_query = ""
            return

        if event.unicode and event.unicode.isprintable():
            # Add character to search query
            self.quick_open_query += event.unicode
            self._search_files_quick_open(self.quick_open_query)

    def _handle_quick_open_click(self, mouse_x, mouse_y):
        """Handle mouse clicks on quick open modal"""
        # Calculate modal bounds (same as rendering)
        modal_width = min(60, self.renderer.char_width - 10)
        modal_height = min(20, self.renderer.char_height - 6)
        modal_start_x = (self.renderer.char_width - modal_width) // 2
        modal_start_y = (self.renderer.char_height - modal_height) // 2

        # Check if click is within modal bounds
        if not (modal_start_x <= mouse_x < modal_start_x + modal_width and
                modal_start_y <= mouse_y < modal_start_y + modal_height):
            # Clicked outside modal - close it
            self.quick_open_active = False
            self.quick_open_query = ""
            self.quick_open_results = []
            return

        # Check if clicking on a result (results start at row 2 of modal)
        result_start_y = modal_start_y + 2
        click_y = mouse_y - result_start_y

        if 0 <= click_y < len(self.quick_open_results):
            filepath = self.quick_open_results[click_y]
            # Skip directories
            if not filepath.endswith('/'):
                filename = filepath.split('/')[-1]
                self._open_file(filepath, filename)
                # Close modal and return to editor
                self.quick_open_active = False
                self.quick_open_query = ""
                self.quick_open_results = []
                # Focus editor
                self.focused_area = 'editor'

    def _handle_terminal_keydown(self, event):
        """Handle keyboard input for terminal"""
        if event.key == pygame.K_RETURN:
            # Execute command
            command = self.terminal_input_buffer.strip()
            if command:
                self._execute_terminal_command(command)
            self.terminal_input_buffer = ""
            self.terminal_history_index = -1

        elif event.key == pygame.K_BACKSPACE:
            if self.terminal_input_buffer:
                self.terminal_input_buffer = self.terminal_input_buffer[:-1]

        elif event.key == pygame.K_UP:
            # Navigate command history
            if self.terminal_history:
                if self.terminal_history_index == -1:
                    self.terminal_history_index = len(self.terminal_history) - 1
                elif self.terminal_history_index > 0:
                    self.terminal_history_index -= 1
                if 0 <= self.terminal_history_index < len(self.terminal_history):
                    self.terminal_input_buffer = self.terminal_history[self.terminal_history_index]

        elif event.key == pygame.K_DOWN:
            # Navigate command history forward
            if self.terminal_history_index >= 0:
                self.terminal_history_index += 1
                if self.terminal_history_index >= len(self.terminal_history):
                    self.terminal_history_index = -1
                    self.terminal_input_buffer = ""
                else:
                    self.terminal_input_buffer = self.terminal_history[self.terminal_history_index]

        elif event.unicode and event.unicode.isprintable():
            # Add character to input buffer
            self.terminal_input_buffer += event.unicode

    def _execute_terminal_command(self, command):
        """Run a command through the main shell, capturing output in this panel."""
        shell = getattr(self.previous_state, "shell", None)
        hidden = bool(shell and shell.session and shell.session.secret)
        self.terminal_output_lines.append(f"{self._get_terminal_prompt()}{'' if hidden else command}")
        if shell is None:
            self.terminal_output_lines.append(f"Command: {command}")
        else:
            original_ui = shell.ui
            shell.ui = _EmbeddedTerminalUI(self, original_ui)
            try:
                shell.submit(command)
            finally:
                shell.ui = original_ui
            self.terminal_history = [h for h in shell.history[-100:]]

        # Auto-scroll to bottom
        self.terminal_scroll_offset = 0

        # Trim output if too long
        if len(self.terminal_output_lines) > 1000:
            self.terminal_output_lines = self.terminal_output_lines[-1000:]


class _EmbeddedTerminalUI:
    """ShellUI adapter that prints into the editor's terminal panel."""

    def __init__(self, editor, main_ui):
        self.editor = editor
        self.main_ui = main_ui

    @property
    def width(self) -> int:
        return max(20, self.editor.renderer.char_width - 4)

    def write(self, line) -> None:
        self.editor.terminal_output_lines.append(str(line))

    def typed(self, lines, delay=30) -> None:
        for line in lines:
            self.write(line)

    def clear(self) -> None:
        self.editor.terminal_output_lines = []

    def launch(self, factory) -> None:
        self.editor.game.change_state(factory(self.editor.game, self.editor))

    def quit(self) -> None:
        self.main_ui.quit()

    def notify(self, title, body) -> None:
        self.main_ui.notify(title, body)
        self.editor._show_status(f"{title}: {body}")
