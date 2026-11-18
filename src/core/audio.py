"""
Procedural sound effects. Everything is synthesised at startup from a few
numbers (no audio files), and every call is a silent no-op when there's no
audio device.
"""

from __future__ import annotations

import random
import time
from array import array

import pygame

# name -> (waveform, start Hz, end Hz, seconds, volume)
SOUNDS = {
    "graze": ("square", 1800, 2400, 0.03, 0.10),
    "hit": ("noise", 600, 80, 0.45, 0.45),
    "bomb": ("noise", 220, 30, 0.9, 0.55),
    "bomb_charged": ("square", 660, 990, 0.12, 0.18),
    "wave": ("triangle", 440, 660, 0.18, 0.22),
    "warning": ("square", 220, 180, 0.6, 0.25),
    "phase": ("triangle", 330, 880, 0.25, 0.25),
    "boss_defeated": ("noise", 400, 20, 1.6, 0.6),
    "achievement": ("arp", 523, 1047, 0.36, 0.25),
    "depleted": ("triangle", 880, 440, 0.1, 0.12),
    "pause": ("triangle", 600, 300, 0.08, 0.15),
}
_MIN_GAP = {"graze": 0.05, "depleted": 0.05}


def _synth(kind: str, f0: float, f1: float, seconds: float, volume: float, rate: int) -> array:
    n = max(1, int(rate * seconds))
    out = array("h")
    phase = 0.0
    rng = random.Random(f0 * 7 + f1)
    held = 0.0
    for i in range(n):
        t = i / n
        if kind == "arp":  # three rising steps
            freq = f0 * (1.0, 1.26, 1.5, 2.0)[min(3, int(t * 4))]
        else:
            freq = f0 + (f1 - f0) * t
        phase += freq / rate
        if kind == "square":
            v = 1.0 if (phase % 1.0) < 0.5 else -1.0
        elif kind in ("triangle", "arp"):
            v = 4 * abs((phase % 1.0) - 0.5) - 1
        else:  # noise, resampled at `freq` for a pitched rumble
            if (phase % 1.0) < freq / rate or i == 0:
                held = rng.uniform(-1, 1)
            v = held
        env = (1 - t) ** 2 if kind != "arp" else (1 - t)
        attack = min(1.0, i / (rate * 0.004))
        out.append(int(v * env * attack * volume * 32767))
    return out


class Sfx:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self._last: dict[str, float] = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            rate, _size, channels = pygame.mixer.get_init()
            for name, spec in SOUNDS.items():
                mono = _synth(*spec, rate=rate)
                if channels == 2:
                    stereo = array("h")
                    for s in mono:
                        stereo.append(s)
                        stereo.append(s)
                    mono = stereo
                self.sounds[name] = pygame.mixer.Sound(buffer=mono.tobytes())
        except (pygame.error, TypeError, ValueError):
            self.sounds = {}

    def play(self, name: str) -> None:
        if not self.enabled:
            return
        sound = self.sounds.get(name)
        if sound is None:
            return
        now = time.monotonic()
        if now - self._last.get(name, 0.0) < _MIN_GAP.get(name, 0.0):
            return
        self._last[name] = now
        sound.play()

