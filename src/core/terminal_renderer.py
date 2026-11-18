"""
Terminal-style renderer.

Everything in the game draws into a character grid (``buffer`` +
``color_buffer`` + optional ``bg_buffer``); ``render()`` turns that grid into
pixels. Glyph surfaces are cached, so a full 160x75 frame is a single batched
blit instead of ~12k font renders.

Juice lives here too: screen shake, full-screen flashes, CRT scanlines and
colour themes.
"""

from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

import pygame

# Monospace fonts in order of preference. Override with $ASCII_BULLET_FONT.
FONT_PREFERENCES = (
    "menlo", "dejavusansmono", "jetbrainsmono", "cascadiamono", "consolas",
    "liberationmono", "couriernew", "courier", "freemono",
)
_GLYPH_CACHE_LIMIT = 6000
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def resource_path(*parts: str) -> str:
    """Resolve a bundled resource in dev checkouts and PyInstaller builds."""
    base = getattr(sys, "_MEIPASS", None)
    root = Path(base) if base else Path(__file__).resolve().parent.parent.parent
    return str(root.joinpath(*parts))


def load_themes() -> dict:
    with open(_DATA_DIR / "themes.json", encoding="utf-8") as f:
        raw = json.load(f)
    return {name: {k: tuple(v) for k, v in theme.items()} for name, theme in raw.items()}


def _find_font_path(bold: bool = True) -> str | None:
    override = os.environ.get("ASCII_BULLET_FONT")
    candidates = ((override,) if override else ()) + FONT_PREFERENCES
    for name in candidates:
        if name and os.path.isfile(name):
            return name
        path = pygame.font.match_font(name, bold=bold) if name else None
        if path:
            return path
    return None


class TerminalRenderer:
    """Character-grid renderer with a retro terminal look."""

    # Class-level defaults; each instance gets its own copy so themes can swap.
    COLORS = {
        "bg": (10, 10, 15),
        "fg": (0, 255, 0),
        "title_bar": (15, 15, 20),
        "menu_selected": (0, 255, 0),
        "menu_normal": (120, 255, 120),
        "title": (100, 255, 100),
        "dim": (40, 120, 40),
        "accent": (0, 220, 255),
        "warn": (255, 200, 0),
        "error": (255, 70, 70),
    }

    def __init__(self, width: int = 80, height: int = 50, cell_size: int = 12):
        self.initial_width = width
        self.initial_height = height
        self.font_size = cell_size
        self.COLORS = dict(TerminalRenderer.COLORS)

        pygame.init()
        font_path = _find_font_path(bold=True)
        self.font = pygame.font.Font(font_path, cell_size)
        self.title_font = pygame.font.Font(font_path, 10)

        # Cell metrics come from the font itself.
        self.char_pixel_width = max(1, self.font.size("M")[0])
        self.char_pixel_height = self.font.get_linesize()
        self.cell_width = self.char_pixel_width
        self.cell_height = self.char_pixel_height

        self.frame_thickness = 0
        self.title_bar_height = 20
        self.title_text = "ASCII BULLET HELL"

        # Don't open a window taller/wider than the screen.
        info = pygame.display.Info()
        if info.current_w > 0 and info.current_h > 0:
            max_cols = int(info.current_w * 0.92) // self.cell_width
            max_rows = int(info.current_h * 0.86 - self.title_bar_height) // self.cell_height
            width = max(80, min(width, max_cols))
            height = max(30, min(height, max_rows))

        self.char_width = width
        self.char_height = height
        self._calculate_window_dimensions()

        self.screen = pygame.display.set_mode((self.window_width, self.window_height), pygame.RESIZABLE)
        pygame.display.set_caption("BLTHLL TERMINAL")
        self._set_icon()

        self._glyphs: dict[tuple[str, tuple], pygame.Surface] = {}
        self._missing_glyphs: set[str] = set()
        self._scanlines: pygame.Surface | None = None
        self._resize_buffer(width, height)

        # Effects
        self.shake_time = 0.0
        self.shake_intensity = 0.0
        self.flash_time = 0.0
        self.flash_duration = 1.0
        self.flash_color = (255, 255, 255)
        self.crt_enabled = True
        self.shake_enabled = True

        try:
            self.themes = load_themes()
        except (OSError, ValueError):
            self.themes = {}
        self.theme_name = "phosphor"

        self.clock = pygame.time.Clock()

    # ------------------------------------------------------------- setup
    def _set_icon(self) -> None:
        icon_path = resource_path("src", "assets", "bllthll.png")
        if os.path.exists(icon_path):
            try:
                pygame.display.set_icon(pygame.image.load(icon_path))
            except pygame.error:
                pass

    def _calculate_window_dimensions(self) -> None:
        self.terminal_width = self.char_width * self.cell_width
        self.terminal_height = self.char_height * self.cell_height
        self.window_width = self.terminal_width + self.frame_thickness * 2
        self.window_height = self.terminal_height + self.frame_thickness * 2 + self.title_bar_height

    def _resize_buffer(self, new_width: int, new_height: int) -> None:
        """Resize the grid, preserving overlapping content."""
        old = getattr(self, "buffer", None)
        old_colors = getattr(self, "color_buffer", None)
        fg = self.COLORS["fg"]
        self.buffer = [[" "] * new_width for _ in range(new_height)]
        self.color_buffer = [[fg] * new_width for _ in range(new_height)]
        self.bg_buffer: list[list[tuple | None]] = [[None] * new_width for _ in range(new_height)]
        if old and old_colors:
            for row in range(min(len(old), new_height)):
                cols = min(len(old[row]), new_width)
                self.buffer[row][:cols] = old[row][:cols]
                self.color_buffer[row][:cols] = old_colors[row][:cols]

    def handle_resize(self, new_width: int, new_height: int) -> None:
        self.screen = pygame.display.set_mode((new_width, new_height), pygame.RESIZABLE)
        self._scanlines = None
        self._sync_grid_to_window()  # so states lay out against the new grid this frame

    # ------------------------------------------------------------ themes
    def set_theme(self, name: str) -> bool:
        theme = self.themes.get(name)
        if not theme:
            return False
        old_fg = self.COLORS["fg"]
        self.COLORS.update(theme)
        self.theme_name = name
        # Recolour anything already drawn in the old default foreground.
        new_fg = self.COLORS["fg"]
        for row in self.color_buffer:
            for i, c in enumerate(row):
                if c == old_fg:
                    row[i] = new_fg
        return True

    # ------------------------------------------------------------ drawing
    def clear(self) -> None:
        fg = self.COLORS["fg"]
        w = self.char_width
        for row in range(self.char_height):
            self.buffer[row] = [" "] * w
            self.color_buffer[row] = [fg] * w
            self.bg_buffer[row] = [None] * w

    def write(self, x: int, y: int, text: str, color=None, bg=None) -> None:
        """Write ``text`` at cell (x, y). Off-grid characters are clipped."""
        if not 0 <= y < self.char_height:
            return
        if color is None:
            color = self.COLORS["fg"]
        row, crow, brow = self.buffer[y], self.color_buffer[y], self.bg_buffer[y]
        width = self.char_width
        for i, char in enumerate(text):
            col = x + i
            if 0 <= col < width:
                row[col] = char
                crow[col] = color
                if bg is not None:
                    brow[col] = bg

    def write_centered(self, y: int, text: str, color=None, bg=None) -> None:
        self.write((self.char_width - len(text)) // 2, y, text, color, bg)

    def fill_bg(self, x: int, y: int, w: int, h: int, bg) -> None:
        for row in range(max(0, y), min(self.char_height, y + h)):
            brow = self.bg_buffer[row]
            for col in range(max(0, x), min(self.char_width, x + w)):
                brow[col] = bg

    def draw_box(self, x: int, y: int, width: int, height: int, color=None, style: str = "ascii") -> None:
        """Draw a box outline. ``style`` is 'ascii' (+-|) or 'line' (box drawing)."""
        if color is None:
            color = self.COLORS["fg"]
        if style == "line":
            tl, tr, bl, br, h, v = "┌", "┐", "└", "┘", "─", "│"
        elif style == "double":
            tl, tr, bl, br, h, v = "╔", "╗", "╚", "╝", "═", "║"
        else:
            tl, tr, bl, br, h, v = "+", "+", "+", "+", "-", "|"
        self.write(x, y, tl + h * (width - 2) + tr, color)
        self.write(x, y + height - 1, bl + h * (width - 2) + br, color)
        for row in range(y + 1, y + height - 1):
            self.write(x, row, v, color)
            self.write(x + width - 1, row, v, color)

    # ------------------------------------------------------------ effects
    def shake(self, intensity: float = 4.0, duration: float = 0.25) -> None:
        """Shake the screen by up to ``intensity`` pixels for ``duration`` s."""
        if not self.shake_enabled:
            return
        self.shake_intensity = max(self.shake_intensity, intensity)
        self.shake_time = max(self.shake_time, duration)

    def flash(self, color=(255, 255, 255), duration: float = 0.15) -> None:
        self.flash_color = color
        self.flash_time = self.flash_duration = max(0.01, duration)

    def update_effects(self, dt_ms: float) -> None:
        dt = dt_ms / 1000.0
        if self.shake_time > 0:
            self.shake_time = max(0.0, self.shake_time - dt)
            if self.shake_time == 0:
                self.shake_intensity = 0.0
        if self.flash_time > 0:
            self.flash_time = max(0.0, self.flash_time - dt)

    def _glyph(self, char: str, color) -> pygame.Surface:
        key = (char, color)
        surf = self._glyphs.get(key)
        if surf is None:
            if char in self._missing_glyphs:
                char = "?"
            elif self.font.metrics(char)[0] is None:
                self._missing_glyphs.add(char)
                char = "?"
            try:
                surf = self.font.render(char, True, color)
            except (pygame.error, UnicodeError):
                surf = self.font.render("?", True, color)
            if len(self._glyphs) > _GLYPH_CACHE_LIMIT:
                self._glyphs.clear()
            self._glyphs[key] = surf
        return surf

    def _get_scanlines(self, w: int, h: int) -> pygame.Surface:
        if self._scanlines is None or self._scanlines.get_size() != (w, h):
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            for y in range(0, h, 3):
                pygame.draw.line(surf, (0, 0, 0, 55), (0, y), (w, y))
            self._scanlines = surf
        return self._scanlines

    # ------------------------------------------------------------- render
    def _sync_grid_to_window(self) -> tuple[int, int]:
        actual_w, actual_h = self.screen.get_size()
        avail_w = actual_w - self.frame_thickness * 2
        avail_h = actual_h - self.frame_thickness * 2 - self.title_bar_height
        cols = max(20, avail_w // self.cell_width)
        rows = max(10, avail_h // self.cell_height)
        if cols != self.char_width or rows != self.char_height:
            self.char_width, self.char_height = cols, rows
            self.terminal_width = cols * self.cell_width
            self.terminal_height = rows * self.cell_height
            self.window_width, self.window_height = actual_w, actual_h
            self._resize_buffer(cols, rows)
        return actual_w, actual_h

    def render(self) -> None:
        actual_w, actual_h = self._sync_grid_to_window()
        bg = self.COLORS["bg"]
        self.screen.fill(bg)

        # Title bar
        pygame.draw.rect(self.screen, self.COLORS["title_bar"], (0, 0, actual_w, self.title_bar_height))
        dots_y = self.title_bar_height // 2
        for i, c in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
            pygame.draw.circle(self.screen, c, (10 + i * 14, dots_y), 4)
        title = self.title_font.render(self.title_text, True, self.COLORS["menu_normal"])
        self.screen.blit(title, ((actual_w - title.get_width()) // 2, (self.title_bar_height - title.get_height()) // 2))
        size = self.title_font.render(f"{self.char_width}x{self.char_height}", True, self.COLORS["dim"])
        self.screen.blit(size, (actual_w - size.get_width() - 8, (self.title_bar_height - size.get_height()) // 2))

        cw, ch = self.cell_width, self.cell_height
        ox, oy = self.frame_thickness, self.title_bar_height + self.frame_thickness
        if self.shake_time > 0 and self.shake_intensity > 0:
            k = self.shake_intensity * min(1.0, self.shake_time / 0.25)
            ox += int(random.uniform(-k, k))
            oy += int(random.uniform(-k, k))

        blits = []
        glyph = self._glyph
        rect = pygame.Rect(0, 0, cw, ch)
        fill = self.screen.fill
        for row_idx in range(min(self.char_height, len(self.buffer))):
            row = self.buffer[row_idx]
            colors = self.color_buffer[row_idx]
            bgs = self.bg_buffer[row_idx]
            py = oy + row_idx * ch
            for col_idx, char in enumerate(row):
                cell_bg = bgs[col_idx]
                if cell_bg is not None:
                    rect.topleft = (ox + col_idx * cw, py)
                    fill(cell_bg, rect)
                if char != " ":
                    blits.append((glyph(char, colors[col_idx]), (ox + col_idx * cw, py)))
        self.screen.fblits(blits)

        if self.flash_time > 0:
            overlay = pygame.Surface((actual_w, actual_h), pygame.SRCALPHA)
            alpha = int(160 * (self.flash_time / self.flash_duration))
            overlay.fill((*self.flash_color, alpha))
            self.screen.blit(overlay, (0, 0))

        if self.crt_enabled:
            self.screen.blit(self._get_scanlines(actual_w, actual_h - self.title_bar_height), (0, self.title_bar_height))

        pygame.display.flip()

    def snapshot_text(self) -> list[str]:
        """Return the current grid as strings (handy for tests and debugging)."""
        return ["".join(row) for row in self.buffer]

    def tick(self, fps: int = 60) -> int:
        return self.clock.tick(fps)

    def quit(self) -> None:
        pygame.quit()
