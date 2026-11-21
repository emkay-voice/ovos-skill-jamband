"""The jam on the screen: the chord now, big; the next ones; who is playing.

An SVG picture sent to the stock SYSTEM_ImageFrame page, so every OVOS GUI
can show it.
"""
from __future__ import annotations

import base64
from html import escape

from .music import Chord
from .styles import PARTS

#: nearly square: big enough on a phone held upright, and fine on a landscape screen
W, H = 1080, 1180
BG, FG, DIM, LIT, OFF = "#101418", "#e8e8e8", "#7a8088", "#ffcc33", "#2a3038"
ICON = {"drums": "🥁", "bass": "🎸", "piano": "🎹", "guitar": "🎸", "organ": "⛪", "strings": "🎻",
        "brass": "🎺", "sax": "🎷", "bandoneon": "🪗"}
COLUMNS = 3


def render(title: str, chord: Chord, upcoming: list[Chord], playing: list[str], names: dict, note: str = "") -> str:
    """The chord now, big; the next four; and the band, three to a row, each
    instrument big enough to see on a phone (lit when it plays)."""
    sans = 'font-family="sans-serif" text-anchor="middle"'
    parts = [f'<rect width="{W}" height="{H}" fill="{BG}"/>',
             f'<text x="{W / 2}" y="62" font-size="36" fill="{DIM}" {sans}>{escape(title)}</text>',
             f'<text x="{W / 2}" y="330" font-size="230" font-weight="bold" fill="{LIT}" {sans}>'
             f'{escape(chord.name)}</text>']
    if note:
        parts.append(f'<text x="{W / 2}" y="118" font-size="44" font-weight="bold" fill="{FG}" {sans}>'
                     f'{escape(note)}</text>')
    for i, c in enumerate(upcoming[:4]):
        x = W / 2 + (i - 1.5) * 200
        parts.append(f'<text x="{x}" y="440" font-size="64" fill="{DIM if i else FG}" {sans}>{escape(c.name)}</text>')
    cell_w, cell_h, top = W / COLUMNS, 220, 490
    for i, p in enumerate(PARTS):
        x = cell_w * (i % COLUMNS + 0.5)
        cy = top + 72 + cell_h * (i // COLUMNS)
        on = p in playing
        faded = "" if on else ' opacity="0.45"'
        parts.append(f'<circle cx="{x}" cy="{cy}" r="72" fill="{LIT if on else OFF}" opacity="{1 if on else 0.5}"/>')
        parts.append(f'<text x="{x}" y="{cy + 26}" font-size="76" text-anchor="middle"'
                     f'{faded}>{ICON[p]}</text>')
        parts.append(f'<text x="{x}" y="{cy + 112}" font-size="34" fill="{FG if on else DIM}" '
                     f'font-weight="{"bold" if on else "normal"}" {sans}>{escape(names.get(p, p))}</text>')
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">{"".join(parts)}</svg>'
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
