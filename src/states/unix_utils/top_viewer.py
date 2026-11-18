"""
Interactive top/process viewer state
"""

import pygame

from src.states.base_state import BaseState


class TopViewerState(BaseState):
    """Interactive process viewer (like Unix top command)"""

    def __init__(self, game, process_manager, previous_state, on_kill=None):
        super().__init__(game)
        self.process_manager = process_manager
        self.on_kill = on_kill  # callable(pid) -> None, runs the shell's `kill`
        self.selected_pid = None
        self.status = ""
        self.previous_state = previous_state
        self.renderer = game.renderer

        # Update timing - use elapsed time to determine when to update
        self.elapsed_time = 0.0
        self.last_update_second = -1  # Track which second we last updated
        self.update_interval = 2  # Update every N seconds

        # Cached data for rendering
        self.cached_processes = []
        self.cached_stats = {
            'total_cpu': 0,
            'total_mem': 0,
            'process_count': 0
        }

        # Scrolling
        self.scroll_offset = 0
        self.max_visible_processes = 15

    def enter(self):
        """Called when entering this state"""
        # Force immediate data load on enter
        self._update_data()

    def exit(self):
        """Called when exiting this state"""
        pass

    def handle_events(self, events):
        """Handle input events"""
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
                    # Quit top viewer
                    self.game.change_state(self.previous_state, call_enter=False)
                elif event.key in (pygame.K_UP, pygame.K_DOWN):
                    self._move_selection(-1 if event.key == pygame.K_UP else 1)
                elif event.key == pygame.K_k and self.selected_pid is not None:
                    if self.on_kill:
                        pid = self.selected_pid
                        self.on_kill(pid)
                        self.status = f"sent SIGTERM to {pid}"
                        self._update_data()
                    else:
                        self.status = "kill: not available here"

    def _selected_index(self) -> int:
        pids = [p.pid for p in self.cached_processes]
        return pids.index(self.selected_pid) if self.selected_pid in pids else 0

    def _move_selection(self, delta: int) -> None:
        if not self.cached_processes:
            return
        idx = max(0, min(len(self.cached_processes) - 1, self._selected_index() + delta))
        self.selected_pid = self.cached_processes[idx].pid
        if idx < self.scroll_offset:
            self.scroll_offset = idx
        elif idx >= self.scroll_offset + self.max_visible_processes:
            self.scroll_offset = idx - self.max_visible_processes + 1

    def _update_data(self):
        """Update the cached process data"""
        self.process_manager.update_cpu_usage()
        self.cached_processes = self.process_manager.get_processes()
        if self.cached_processes and self.selected_pid not in {p.pid for p in self.cached_processes}:
            self.selected_pid = self.cached_processes[0].pid

        # Calculate stats
        self.cached_stats['total_cpu'] = sum(p.cpu for p in self.cached_processes)
        self.cached_stats['total_mem'] = sum(p.mem for p in self.cached_processes)
        self.cached_stats['process_count'] = len(self.cached_processes)

    def update(self, dt):
        """Update state"""
        # Track elapsed time (dt is in milliseconds, convert to seconds)
        self.elapsed_time += dt / 1000.0

        # Calculate current "update second" (which N-second interval we're in)
        current_update_second = int(self.elapsed_time / self.update_interval)

        # Only update data when we cross into a new interval
        if current_update_second != self.last_update_second:
            self.last_update_second = current_update_second
            self._update_data()

    def render(self):
        """Render the top viewer"""
        self.renderer.clear()

        # Use cached data - only updates when interval changes
        processes = self.cached_processes
        total_cpu = self.cached_stats['total_cpu']
        total_mem = self.cached_stats['total_mem']

        row = 1

        # Title
        self.renderer.write(2, row, "TOP - Process Viewer", (0, 255, 255))
        row += 1
        self.renderer.write(2, row, "=" * 50, (100, 100, 100))
        row += 2

        # System info
        self.renderer.write(2, row, f"Processes: {len(processes)} total", (200, 200, 200))
        row += 1

        idle_cpu = max(0, 100 - total_cpu - 2.1)
        self.renderer.write(2, row,
                          f"CPU: {total_cpu:.1f}% user, 2.1% sys, {idle_cpu:.1f}% idle",
                          (200, 200, 200))
        row += 1

        free_mem = max(0, 1024 - total_mem)
        self.renderer.write(2, row,
                          f"Memory: {total_mem:.0f}M used, {free_mem:.0f}M free",
                          (200, 200, 200))
        row += 2

        # Column headers
        header = f"{'PID':<8} {'COMMAND':<20} {'%CPU':<8} {'MEM':<10} {'USER':<8} {'TIME':<10}"
        self.renderer.write(2, row, header, (255, 255, 0))
        row += 1
        self.renderer.write(2, row, "-" * 75, (100, 100, 100))
        row += 1

        # Process list (with scrolling)
        visible_processes = processes[self.scroll_offset:self.scroll_offset + self.max_visible_processes]

        for proc in visible_processes:
            # Highlight high CPU processes
            if proc.cpu > 10.0:
                color = (255, 100, 100)  # Red for high CPU
            elif hasattr(proc, 'is_virus') and proc.is_virus:
                color = (255, 150, 150)  # Slightly red for virus
            else:
                color = (200, 200, 200)  # Normal

            line = f"{proc.pid:<8} {proc.command:<20} {proc.cpu:<7.1f} {proc.mem:.1f}M{'':<5} {proc.user:<8} {proc.time_str:<10}"
            if proc.pid == self.selected_pid:
                self.renderer.write(2, row, line.ljust(75), (10, 10, 15), bg=(0, 200, 120))
            else:
                self.renderer.write(2, row, line, color)
            row += 1

            if row >= self.renderer.char_height - 4:
                break

        # Scroll indicator
        if len(processes) > self.max_visible_processes:
            scroll_info = f"Showing {self.scroll_offset + 1}-{min(self.scroll_offset + self.max_visible_processes, len(processes))} of {len(processes)}"
            self.renderer.write(2, self.renderer.char_height - 3, scroll_info, (150, 150, 150))

        # Help text
        self.renderer.write(2, self.renderer.char_height - 2,
                            "q quit | UP/DOWN select | k kill selected", (100, 100, 255))
        if self.status:
            self.renderer.write(2, self.renderer.char_height - 4, self.status, (255, 200, 0))

        self.renderer.render()

