"""The jam on the screen: the chord now, big; the next ones; who is playing.

An SVG picture sent to the stock SYSTEM_ImageFrame page, so every OVOS GUI
can show it.
"""
from __future__ import annotations

import base64
from html import escape

from .music import Chord
from .styles import PARTS

W, H = 1280, 720
BG, FG, DIM, LIT, OFF = "#101418", "#e8e8e8", "#7a8088", "#ffcc33", "#2a3038"
ICON = {"drums": "🥁", "bass": "🎸", "piano": "🎹", "guitar": "🎸", "organ": "⛪", "strings": "🎻",
        "brass": "🎺", "sax": "🎷", "bandoneon": "🪗"}


def render(title: str, chord: Chord, upcoming: list[Chord], playing: list[str], names: dict) -> str:
    parts = [f'<rect width="{W}" height="{H}" fill="{BG}"/>',
             f'<text x="{W / 2}" y="70" font-size="36" fill="{DIM}" text-anchor="middle" '
             f'font-family="sans-serif">{escape(title)}</text>',
             f'<text x="{W / 2}" y="330" font-size="220" font-weight="bold" fill="{LIT}" text-anchor="middle" '
             f'font-family="sans-serif">{escape(chord.name)}</text>']
    for i, c in enumerate(upcoming[:4]):
        x = W / 2 + (i - 1.5) * 170
        parts.append(f'<text x="{x}" y="430" font-size="56" fill="{DIM if i else FG}" text-anchor="middle" '
                     f'font-family="sans-serif">{escape(c.name)}</text>')
    shown = [p for p in PARTS if p != "bandoneon" or "bandoneon" in playing]
    step = W / (len(shown) + 1)
    for i, p in enumerate(shown):
        x = step * (i + 1)
        on = p in playing
        parts.append(f'<circle cx="{x}" cy="570" r="56" fill="{LIT if on else OFF}" opacity="{1 if on else 0.6}"/>')
        parts.append(f'<text x="{x}" y="592" font-size="56" text-anchor="middle">{ICON[p]}</text>')
        parts.append(f'<text x="{x}" y="664" font-size="24" fill="{FG if on else DIM}" text-anchor="middle" '
                     f'font-family="sans-serif">{escape(names.get(p, p))}</text>')
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">{"".join(parts)}</svg>'
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
