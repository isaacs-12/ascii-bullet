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
            previous_state: State to return to when done
        """
        super().__init__(game)
        self.filesystem = filesystem
        self.previous_state = previous_state
        
        # Sidebar state
        self.sidebar_width = 20  # Character width of sidebar
        self.sidebar_drag_x = None  # X position when dragging (None if not dragging)
        self.sidebar_min_width = 10
        self.sidebar_max_width = 40
        
        # File tree state
        self.expanded_dirs = set()  # Set of expanded directory paths
        self.selected_file = None  # Currently selected file in sidebar
        
        # Tab system
        self.open_tabs = []  # List of (filename, full_path) tuples
        self.active_tab_index = 0  # Index of currently active tab
        
        # Editor state for active tab
        self.editor_scroll_y = 0  # Vertical scroll position (line offset)
        self.cursor_line = 0
        self.cursor_col = 0
        
        # File contents cache: full_path -> list of lines
        self.file_contents = {}
        
        # Initialize with current directory expanded
        current_path = self.filesystem.get_pwd()
        self.expanded_dirs.add(current_path)
        
        # Message/status
        self.status_message = "Code Editor | ESC to quit | Click files to open"
        self.status_message_timeout = 0
    
    def enter(self):
        """Called when entering this state"""
        pass
    
    def exit(self):
        """Called when exiting this state"""
        # Auto-save all open files
        self._save_all_files()
    
    def _save_all_files(self):
        """Save all open files"""
        for filename, full_path in self.open_tabs:
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
            # Check if file exists
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
    
    def _open_file(self, full_path, filename):
        """Open a file in a new tab"""
        # Check if already open
        for i, (name, path) in enumerate(self.open_tabs):
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
                self._handle_keydown(event)
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
        if event.key == pygame.K_ESCAPE:
            # Quit editor
            self._save_all_files()
            self.game.change_state(self.previous_state, call_enter=False)
            return
        
        # If no tabs open, ignore most keys
        if len(self.open_tabs) == 0:
            return
        
        filename, full_path = self.open_tabs[self.active_tab_index]
        lines = self.file_contents.get(full_path, [""])
        
        if not lines:
            lines = [""]
        
        # Navigation
        if event.key == pygame.K_UP:
            if self.cursor_line > 0:
                self.cursor_line -= 1
                self.cursor_col = min(self.cursor_col, len(lines[self.cursor_line]))
                # Auto-scroll
                if self.cursor_line < self.editor_scroll_y:
                    self.editor_scroll_y = self.cursor_line
        
        elif event.key == pygame.K_DOWN:
            if self.cursor_line < len(lines) - 1:
                self.cursor_line += 1
                self.cursor_col = min(self.cursor_col, len(lines[self.cursor_line]))
                # Auto-scroll
                editor_height = self.renderer.char_height - 3  # Leave room for tabs and status
                if self.cursor_line >= self.editor_scroll_y + editor_height:
                    self.editor_scroll_y = self.cursor_line - editor_height + 1
        
        elif event.key == pygame.K_LEFT:
            if self.cursor_col > 0:
                self.cursor_col -= 1
        
        elif event.key == pygame.K_RIGHT:
            if self.cursor_col < len(lines[self.cursor_line]):
                self.cursor_col += 1
        
        elif event.key == pygame.K_HOME:
            self.cursor_col = 0
        
        elif event.key == pygame.K_END:
            self.cursor_col = len(lines[self.cursor_line])
        
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
        
        # Editing
        elif event.key == pygame.K_RETURN:
            # Insert new line
            current = lines[self.cursor_line]
            lines[self.cursor_line] = current[:self.cursor_col]
            lines.insert(self.cursor_line + 1, current[self.cursor_col:])
            self.cursor_line += 1
            self.cursor_col = 0
            self.file_contents[full_path] = lines
            # Auto-save
            self._save_file(full_path, lines)
            self._show_status(f"Saved: {filename}")
        
        elif event.key == pygame.K_BACKSPACE:
            # Delete character
            if self.cursor_col > 0:
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
            # Insert character
            line = lines[self.cursor_line]
            lines[self.cursor_line] = line[:self.cursor_col] + event.unicode + line[self.cursor_col:]
            self.cursor_col += 1
            self.file_contents[full_path] = lines
            # Auto-save
            self._save_file(full_path, lines)
            self._show_status(f"Saved: {filename}")
    
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
            
            # Check if clicking on sidebar drag handle (within 1 character width)
            if abs(mouse_x - self.sidebar_width) <= 1:
                self.sidebar_drag_x = event.pos[0]
            
            # Check if clicking in sidebar
            elif mouse_x < self.sidebar_width:
                self._handle_sidebar_click(mouse_x, mouse_y)
            
            # Check if clicking on tabs
            elif mouse_x > self.sidebar_width + 1 and mouse_y < 2:
                self._handle_tab_click(mouse_x, mouse_y)
            
            # Check if clicking in editor area (below tabs)
            elif mouse_x > self.sidebar_width + 1 and mouse_y >= 2:
                self._handle_editor_click(mouse_x, mouse_y)
    
    def _handle_sidebar_click(self, mouse_x, mouse_y):
        """Handle clicks in the sidebar"""
        # Account for sidebar title (row 0)
        click_y = mouse_y - 1
        
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
    
    def _handle_mouse_motion(self, event):
        """Handle mouse motion (for dragging sidebar)"""
        if self.sidebar_drag_x is not None and event.buttons[0]:  # Left button held
            # Calculate new sidebar width
            new_width_chars = event.pos[0] // self.renderer.cell_width
            new_width_chars = max(self.sidebar_min_width, min(self.sidebar_max_width, new_width_chars))
            self.sidebar_width = new_width_chars
    
    def _handle_mouse_wheel(self, event):
        """Handle mouse wheel scrolling"""
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
                self.status_message = "VSCode Editor | ESC to quit | Click files to open"
    
    def render(self):
        """Render the editor"""
        self.renderer.clear()
        
        # Draw sidebar
        self._render_sidebar()
        
        # Draw divider
        divider_x = self.sidebar_width
        for y in range(self.renderer.char_height):
            self.renderer.write(divider_x, y, f"|", (150, 150, 150))
        
        # Draw editor area
        self._render_editor()
        
        # Draw status bar
        self._render_status_bar()
        
        self.renderer.render()
    
    def _render_sidebar(self):
        """Render the file tree sidebar"""
        # Sidebar title
        title = "FILES"
        self.renderer.write(0, 0, title, (200, 200, 200))
        
        # Get file tree
        tree = self._get_file_tree()
        
        # Render tree items
        start_y = 1
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
    
    def _render_editor(self):
        """Render the editor pane"""
        editor_start_x = self.sidebar_width + 2
        
        # Draw tabs
        self._render_tabs(editor_start_x)
        
        # Draw editor content
        if len(self.open_tabs) > 0:
            filename, full_path = self.open_tabs[self.active_tab_index]
            lines = self.file_contents.get(full_path, [""])
            
            if not lines:
                lines = [""]
            
            # Calculate visible area
            editor_height = self.renderer.char_height - 3  # Leave room for tabs and status
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
                
                # Check if it's a Python file
                is_python = filename.endswith('.py')
                
                if is_python:
                    # Apply syntax highlighting
                    tokens = self._python_syntax_highlight(line)
                    x_offset = 0
                    for token_type, token_text in tokens:
                        if token_type == 'keyword':
                            color = (100, 200, 255)  # Light blue
                        elif token_type == 'string':
                            color = (200, 255, 100)  # Light green
                        elif token_type == 'comment':
                            color = (150, 150, 150)  # Gray
                        elif token_type == 'function':
                            color = (255, 200, 100)  # Orange/yellow for function calls
                        elif token_type == 'number':
                            color = (150, 200, 255)  # Light blue for numbers
                        else:
                            color = (255, 255, 255)  # White
                        
                        # Write token
                        for char in token_text:
                            if line_start_x + x_offset < self.renderer.char_width:
                                # Handle special characters that might break rendering
                                try:
                                    self.renderer.write(line_start_x + x_offset, y, char, color)
                                except:
                                    self.renderer.write(line_start_x + x_offset, y, "?", color)
                                x_offset += 1
                else:
                    # No syntax highlighting
                    max_width = self.renderer.char_width - line_start_x
                    display_line = line[:max_width]
                    self.renderer.write(line_start_x, y, display_line, (255, 255, 255))
                
                # Show cursor on current line
                if i == self.cursor_line:
                    cursor_x = line_start_x + self.cursor_col
                    if cursor_x < self.renderer.char_width:
                        # Show cursor as block
                        char_at_cursor = line[self.cursor_col] if self.cursor_col < len(line) else " "
                        # Draw cursor by overwriting the character
                        if self.cursor_col < len(line):
                            # Save original char and color, then draw cursor
                            orig_char = line[self.cursor_col]
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
        
        for i, (filename, full_path) in enumerate(self.open_tabs):
            is_active = (i == self.active_tab_index)
            
            # Tab background
            tab_text = f" {filename} [X] "
            tab_color = (200, 200, 200) if is_active else (100, 100, 100)
            
            # Draw tab
            x = start_x
            for char in tab_text:
                if x < self.renderer.char_width:
                    self.renderer.write(x, y, char, tab_color)
                    x += 1
            
            start_x = x + 1
    
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
