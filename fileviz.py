#!/usr/bin/env python3
"""Proof of concept: show a text file as hex, then animate it into ASCII.

Usage:
    uv run fileviz.py <file>

The file is checked with the system `file` command first; anything that is
not "ASCII text" exits without opening a window.
"""

import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from math import sin, pi
from pathlib import Path

import pygame

BYTES_PER_ROW = 64
FPS = 60
HOLD = 1.0      # seconds the hex view sits still before anything moves
SPREAD = 1.6    # seconds over which byte departures are staggered (wave, top-left to bottom-right)
FLIGHT = 0.8    # seconds each byte spends in the air
MORPH = 0.5     # seconds for the hex -> character crossfade
ARC = 18        # pixels a byte rises during its flight
MARGIN = 24
GAP = 64        # space between the hex grid and the ASCII area
MAX_WINDOW_FRACTION = 0.9  # keep the window within this share of the screen height

BG = (16, 18, 24)
HEX_COLOR = (92, 120, 150)
HEX_FLY_COLOR = (255, 214, 102)
CHAR_COLOR = (150, 230, 170)
DOT_COLOR = (90, 90, 100)
LABEL_COLOR = (200, 200, 210)

FILE_CMD = shutil.which("file") or "/usr/bin/file"


def identify(path: Path) -> str:
    """Return the description the `file` command gives for `path`."""
    result = subprocess.run(
        [FILE_CMD, "--brief", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def printable(byte: int) -> str:
    return chr(byte) if 0x20 <= byte < 0x7F else "."


@dataclass
class Flight:
    byte: int
    src: tuple[int, int]
    dst: tuple[int, int]
    delay: float


class Scene:
    """Lays out the hex and ASCII grids and draws the animation at a given time."""

    def __init__(self, data: bytes, title: str, font: pygame.font.Font, max_rows: int):
        self.font = font
        self.cell_w = font.size("00")[0] + 4   # one hex byte plus spacing
        self.char_w = font.size("M")[0]        # monospace: every glyph has this width
        self.line_h = font.get_linesize()

        self.hex_x = MARGIN
        self.ascii_x = MARGIN + BYTES_PER_ROW * self.cell_w + GAP
        self.top = MARGIN + self.line_h * 2 + 12
        self.width = self.ascii_x + BYTES_PER_ROW * self.char_w + MARGIN

        total_rows = -(-len(data) // BYTES_PER_ROW)
        self.rows = min(total_rows, max_rows)
        shown = min(len(data), self.rows * BYTES_PER_ROW)
        self.height = self.top + self.rows * self.line_h + MARGIN

        if shown < len(data):
            title += f"  -  showing first {self.rows} of {total_rows} rows"
        self.title = title

        # Pre-render every glyph once; the animation only blits them.
        self.hex_static = [font.render(f"{b:02X}", True, HEX_COLOR) for b in range(256)]
        self.hex_fly = [font.render(f"{b:02X}", True, HEX_FLY_COLOR) for b in range(256)]
        self.chars = [
            font.render(printable(b), True, CHAR_COLOR if 0x20 <= b < 0x7F else DOT_COLOR)
            for b in range(256)
        ]
        self.label_hex = font.render("HEX", True, LABEL_COLOR)
        self.label_ascii = font.render("ASCII", True, LABEL_COLOR)
        self.title_surf = font.render(self.title, True, LABEL_COLOR)

        self.flights: list[Flight] = []
        for i in range(shown):
            row, col = divmod(i, BYTES_PER_ROW)
            y = self.top + row * self.line_h
            src = (self.hex_x + col * self.cell_w, y)
            dst = (self.ascii_x + col * self.char_w, y)
            delay = SPREAD * i / max(1, shown - 1)
            self.flights.append(Flight(data[i], src, dst, delay))

        self.duration = HOLD + SPREAD + FLIGHT + MORPH

    def draw(self, screen: pygame.Surface, elapsed: float) -> None:
        screen.fill(BG)
        screen.blit(self.title_surf, (MARGIN, MARGIN))
        label_y = MARGIN + self.line_h + 6
        screen.blit(self.label_hex, (self.hex_x, label_y))
        screen.blit(self.label_ascii, (self.ascii_x, label_y))

        # The hex grid stays put; the flying bytes are copies of it.
        for f in self.flights:
            screen.blit(self.hex_static[f.byte], f.src)

        for f in self.flights:
            t = elapsed - HOLD - f.delay
            if t < 0:
                continue

            if t < FLIGHT:
                p = smoothstep(t / FLIGHT)
                x = lerp(f.src[0], f.dst[0], p)
                y = lerp(f.src[1], f.dst[1], p) - ARC * sin(pi * p)
                glyph = self.hex_fly[f.byte]
                glyph.set_alpha(255)
                screen.blit(glyph, (round(x), round(y)))
                continue

            # Arrived: crossfade the hex copy into the character.
            m = max(0.0, min(1.0, (t - FLIGHT) / MORPH))
            hex_glyph = self.hex_fly[f.byte]
            hex_glyph.set_alpha(round(255 * (1 - m)))
            screen.blit(hex_glyph, f.dst)
            char_glyph = self.chars[f.byte]
            char_glyph.set_alpha(round(255 * m))
            screen.blit(char_glyph, f.dst)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {Path(argv[0]).name} <file>", file=sys.stderr)
        return 2

    path = Path(argv[1])
    if not path.is_file():
        print(f"error: {path} is not a file", file=sys.stderr)
        return 2

    description = identify(path)
    if not description.startswith("ASCII text"):
        print(f"{path}: {description}. Not ASCII text, exiting.", file=sys.stderr)
        return 1

    data = path.read_bytes()

    pygame.init()
    font = pygame.font.SysFont("monospace", 13)

    desktop_h = pygame.display.Info().current_h
    max_h = int(desktop_h * MAX_WINDOW_FRACTION) if desktop_h > 0 else 900
    line_h = font.get_linesize()
    top = MARGIN + line_h * 2 + 12
    max_rows = max(1, (max_h - top - MARGIN) // line_h)

    scene = Scene(data, f"{path.name}  ({description})", font, max_rows)
    screen = pygame.display.set_mode((scene.width, scene.height))
    pygame.display.set_caption(f"fileviz - {path.name}")
    clock = pygame.time.Clock()

    start = time.perf_counter()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_q):
                running = False

        elapsed = time.perf_counter() - start
        scene.draw(screen, elapsed)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
