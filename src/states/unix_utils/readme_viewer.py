"""
Markdown README viewer state
Renders markdown files with formatting in the terminal
"""

import re

import pygame

from src.states.base_state import BaseState


class ReadmeViewerState(BaseState):
    """Viewer for rendering markdown README files"""

    def __init__(self, game, filesystem, filename, previous_state):
        super().__init__(game)
        self.filesystem = filesystem
        self.filename = filename
        self.previous_state = previous_state

        # Load and parse the file
        success, content = filesystem.read_file(filename)
        if success:
            if isinstance(content, list):
                raw_text = '\n'.join(str(line) for line in content)
            else:
                raw_text = str(content)
            self.parsed_lines = self._parse_markdown(raw_text)
        else:
            self.parsed_lines = [
                {'type': 'error', 'text': f"Error: {content}"}
            ]

        # Scrolling
        self.scroll_offset = 0
        self.max_visible_lines = self.renderer.char_height - 2  # Leave room for help text

    def _parse_markdown(self, text):
        """
        Parse markdown text into structured lines with formatting

        Returns:
            list: List of dicts with 'type' and 'text' keys, plus formatting info
        """
        lines = text.split('\n')
        parsed = []
        in_code_block = False
        code_block_language = None

        for line in lines:
            stripped = line.strip()

            # Code blocks
            if stripped.startswith('```'):
                if in_code_block:
                    in_code_block = False
                    code_block_language = None
                    parsed.append({'type': 'code_end'})
                else:
                    in_code_block = True
                    # Extract language if present
                    lang = stripped[3:].strip()
                    code_block_language = lang if lang else None
                    parsed.append({'type': 'code_start', 'language': code_block_language})
                continue

            if in_code_block:
                parsed.append({'type': 'code', 'text': line})
                continue

            # Horizontal rules
            if re.match(r'^[-*_]{3,}$', stripped):
                parsed.append({'type': 'hr'})
                continue

            # Empty lines
            if not stripped:
                parsed.append({'type': 'empty'})
                continue

            # Headers (ATX style: # Header)
            header_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            if header_match:
                level = len(header_match.group(1))
                text = header_match.group(2).strip()
                parsed.append({'type': 'header', 'level': level, 'text': text})
                continue

            # Headers (Setext style: === or ---)
            if len(parsed) > 0 and parsed[-1]['type'] == 'text':
                if re.match(r'^={3,}$', stripped):
                    parsed[-1] = {'type': 'header', 'level': 1, 'text': parsed[-1]['text']}
                    continue
                elif re.match(r'^-{3,}$', stripped):
                    parsed[-1] = {'type': 'header', 'level': 2, 'text': parsed[-1]['text']}
                    continue

            # Lists (unordered: -, *, +)
            list_match = re.match(r'^(\s*)([-*+])\s+(.+)$', line)
            if list_match:
                indent = len(list_match.group(1))
                text = list_match.group(3)
                parsed.append({'type': 'list_item', 'indent': indent, 'text': text})
                continue

            # Lists (ordered: 1., 2., etc.)
            ordered_list_match = re.match(r'^(\s*)(\d+\.)\s+(.+)$', line)
            if ordered_list_match:
                indent = len(ordered_list_match.group(1))
                text = ordered_list_match.group(3)
                parsed.append({'type': 'list_item', 'indent': indent, 'text': text, 'ordered': True})
                continue

            # Regular text with inline formatting
            parsed.append({'type': 'text', 'text': line})

        return parsed

    def _parse_inline_formatting(self, text):
        """
        Parse inline markdown formatting (bold, italic, code, links)

        Returns:
            list: List of segments with 'text' and 'style' keys
        """
        if not text:
            return [{'text': '', 'style': 'normal'}]

        segments = []
        remaining = text

        while remaining:
            # Code spans (backticks) - highest priority
            code_match = re.search(r'`([^`]+)`', remaining)
            if code_match:
                # Add text before code
                before = remaining[:code_match.start()]
                if before:
                    segments.append({'text': before, 'style': 'normal'})
                # Add code segment
                segments.append({'text': code_match.group(1), 'style': 'code'})
                # Continue with remaining text
                remaining = remaining[code_match.end():]
                continue

            # Bold (**text** or __text__) - check for double markers
            bold_match = re.search(r'(\*\*|__)(.+?)\1', remaining)
            if bold_match:
                # Add text before bold
                before = remaining[:bold_match.start()]
                if before:
                    segments.append({'text': before, 'style': 'normal'})
                # Add bold segment
                segments.append({'text': bold_match.group(2), 'style': 'bold'})
                # Continue with remaining text
                remaining = remaining[bold_match.end():]
                continue

            # Italic (*text* or _text_) - single markers, but not if part of bold
            italic_match = re.search(r'(?<!\*)\*([^*\s][^*]*?)\*(?!\*)', remaining)
            if not italic_match:
                italic_match = re.search(r'(?<!_)_([^_\s][^_]*?)_(?!_)', remaining)

            if italic_match:
                # Add text before italic
                before = remaining[:italic_match.start()]
                if before:
                    segments.append({'text': before, 'style': 'normal'})
                # Add italic segment
                segments.append({'text': italic_match.group(1), 'style': 'italic'})
                # Continue with remaining text
                remaining = remaining[italic_match.end():]
                continue

            # No more formatting found
            if remaining:
                segments.append({'text': remaining, 'style': 'normal'})
            break

        return segments if segments else [{'text': text, 'style': 'normal'}]

    def _word_wrap(self, text, max_width):
        """Word wrap text to fit within max_width"""
        words = text.split(' ')
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            word_len = len(word)
            if current_length + word_len + 1 <= max_width:
                current_line.append(word)
                current_length += word_len + 1
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = word_len

        if current_line:
            lines.append(' '.join(current_line))

        return lines if lines else ['']

    def handle_events(self, events):
        """Handle input events"""
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
                    # Quit viewer
                    self.game.change_state(self.previous_state, call_enter=False)
                elif event.key == pygame.K_UP:
                    # Scroll up
                    self.scroll_offset = max(0, self.scroll_offset - 1)
                elif event.key == pygame.K_DOWN:
                    # Scroll down
                    max_scroll = max(0, len(self.parsed_lines) - self.max_visible_lines)
                    self.scroll_offset = min(max_scroll, self.scroll_offset + 1)
                elif event.key == pygame.K_PAGEUP:
                    # Scroll up by page
                    self.scroll_offset = max(0, self.scroll_offset - self.max_visible_lines)
                elif event.key == pygame.K_PAGEDOWN:
                    # Scroll down by page
                    max_scroll = max(0, len(self.parsed_lines) - self.max_visible_lines)
                    self.scroll_offset = min(max_scroll, self.scroll_offset + self.max_visible_lines)
                elif event.key == pygame.K_HOME:
                    # Scroll to top
                    self.scroll_offset = 0
                elif event.key == pygame.K_END:
                    # Scroll to bottom
                    max_scroll = max(0, len(self.parsed_lines) - self.max_visible_lines)
                    self.scroll_offset = max_scroll

    def update(self, dt):
        """Update state"""
        pass

    def render(self):
        """Render the markdown viewer"""
        self.renderer.clear()

        # Calculate visible lines
        visible_lines = self.parsed_lines[self.scroll_offset:self.scroll_offset + self.max_visible_lines]

        row = 1
        max_width = self.renderer.char_width - 2  # Leave margins

        for line_data in visible_lines:
            if row >= self.renderer.char_height - 2:
                break

            line_type = line_data.get('type')

            if line_type == 'header':
                level = line_data.get('level', 1)
                text = line_data.get('text', '')

                # Headers in different colors and sizes
                if level == 1:
                    color = self.renderer.COLORS['title']
                    # Underline with =
                    self.renderer.write(1, row, text[:max_width], color)
                    row += 1
                    if row < self.renderer.char_height - 2:
                        self.renderer.write(1, row, '=' * min(len(text), max_width), color)
                elif level == 2:
                    color = self.renderer.COLORS['menu_selected']
                    self.renderer.write(1, row, text[:max_width], color)
                    row += 1
                    if row < self.renderer.char_height - 2:
                        self.renderer.write(1, row, '-' * min(len(text), max_width), color)
                else:
                    # Smaller headers
                    prefix = '#' * level + ' '
                    color = self.renderer.COLORS['menu_normal']
                    self.renderer.write(1, row, (prefix + text)[:max_width], color)

                row += 1

            elif line_type == 'code_start':
                language = line_data.get('language', '')
                if language:
                    self.renderer.write(1, row, f"```{language}", self.renderer.COLORS['menu_normal'])
                else:
                    self.renderer.write(1, row, "```", self.renderer.COLORS['menu_normal'])
                row += 1

            elif line_type == 'code':
                # Code blocks in a box with different color
                code_text = line_data.get('text', '')
                # Truncate to fit
                display_text = code_text[:max_width]
                # Use a slightly different green for code
                code_color = (100, 255, 100)  # Slightly dimmer green
                self.renderer.write(1, row, display_text, code_color)
                row += 1

            elif line_type == 'code_end':
                self.renderer.write(1, row, "```", self.renderer.COLORS['menu_normal'])
                row += 1

            elif line_type == 'hr':
                # Horizontal rule
                hr_char = '-'
                self.renderer.write(1, row, hr_char * max_width, self.renderer.COLORS['menu_normal'])
                row += 1

            elif line_type == 'list_item':
                indent = line_data.get('indent', 0)
                text = line_data.get('text', '')
                is_ordered = line_data.get('ordered', False)

                # List marker
                marker = "• " if not is_ordered else "1. "
                indent_str = ' ' * (indent // 2)  # Approximate indent
                full_text = indent_str + marker + text

                # Word wrap if needed
                wrapped = self._word_wrap(full_text, max_width)
                for wrapped_line in wrapped:
                    if row >= self.renderer.char_height - 2:
                        break
                    self.renderer.write(1, row, wrapped_line[:max_width], self.renderer.COLORS['fg'])
                    row += 1

            elif line_type == 'text':
                text = line_data.get('text', '')

                # Parse inline formatting
                segments = self._parse_inline_formatting(text)

                # Render segments with proper word wrapping and color
                current_x = 1
                current_segments = []  # List of (text, color) tuples for current line

                for segment in segments:
                    segment_text = segment['text']
                    style = segment['style']

                    # Choose color based on style
                    if style == 'bold':
                        color = self.renderer.COLORS['title']
                    elif style == 'italic':
                        color = self.renderer.COLORS['menu_normal']
                    elif style == 'code':
                        color = (100, 255, 100)
                    else:
                        color = self.renderer.COLORS['fg']

                    # Word wrap the segment
                    words = segment_text.split(' ')
                    for word in words:
                        word_with_space = word + ' '
                        word_len = len(word_with_space)

                        if current_x + word_len > max_width:
                            # Render current line
                            if current_segments:
                                line_text = ''.join(seg[0] for seg in current_segments)
                                # For simplicity, use the first segment's color
                                # In a more advanced version, we'd render each segment separately
                                self.renderer.write(1, row, line_text[:max_width], current_segments[0][1])
                                row += 1
                                if row >= self.renderer.char_height - 2:
                                    break
                            # Start new line
                            current_segments = [(word_with_space, color)]
                            current_x = 1 + word_len
                        else:
                            current_segments.append((word_with_space, color))
                            current_x += word_len

                # Render remaining line
                if current_segments and row < self.renderer.char_height - 2:
                    line_text = ''.join(seg[0] for seg in current_segments)
                    self.renderer.write(1, row, line_text[:max_width], current_segments[0][1])
                    row += 1

            elif line_type == 'empty':
                row += 1

            elif line_type == 'error':
                error_text = line_data.get('text', 'Error')
                self.renderer.write(1, row, error_text[:max_width], (255, 100, 100))
                row += 1

        # Help text at bottom
        help_text = "Press 'q' or ESC to quit | UP/DOWN/PGUP/PGDN to scroll | HOME/END to jump"
        self.renderer.write(1, self.renderer.char_height - 1, help_text[:max_width], self.renderer.COLORS['menu_normal'])

        self.renderer.render()
