"""The band's styles: what each part plays, a bar at a time.

A part's bar is a list of notes ["note", beat, channel, pitch, velocity,
beats]; the jam turns beats into seconds and sends them. Each style has its
groove for every part, so "add the bass" in a swing gets a walking bass, in
reggae a one-drop bass, in disco octaves.

Parts: drums, bass, piano, guitar, organ, strings, brass, sax, bandoneon.

The styles themselves are data: styles/<name>.json - tempo, key, chords,
the band in the order it comes in, General MIDI programs, the drum pattern,
the bass's kind and the comping rhythm of each part. A new file is a new
style (its name is the file's; add the words for it to each locale's
<name>.voc).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .music import NAMES, Chord, Key, note_in, voicing

CHANNEL = {"drums": 9, "bass": 1, "piano": 2, "guitar": 3, "strings": 4, "brass": 5,
           "organ": 6, "sax": 7, "bandoneon": 8}
PARTS = list(CHANNEL)

# General MIDI drum keys
KICK, RIM, SNARE, CLAP, HAT, PEDAL, OPEN, CRASH, RIDE, TOM = 36, 37, 38, 39, 42, 44, 46, 49, 51, 45


@dataclass
class Style:
    name: str
    tempo: int
    key: Key
    progression: list[str]          # degrees, a bar each
    programs: dict                  # part -> GM program
    band: list[str]                 # "the whole band": the parts in the order they come in
    swing: bool = False
    drums: list = field(default_factory=list)    # [(beat, key, velocity)] a bar
    bass: str = "roots"
    comp: dict = field(default_factory=dict)     # part -> [(beat, beats)] chord hits


#: drums by name, as the style files write them
DRUMS = {"kick": KICK, "rim": RIM, "snare": SNARE, "clap": CLAP, "hat": HAT, "pedal": PEDAL, "open": OPEN,
         "crash": CRASH, "ride": RIDE, "tom": TOM}
#: how a bass can walk (bar_notes below plays each)
BASSES = ("walking", "boogie", "eighths", "octaves", "funk", "onedrop", "bossa", "tango", "roots")
STYLE_DIR = Path(__file__).resolve().parent / "styles"


def parse_key(text: str) -> Key:
    """"F", "Em", "C#m", "Bb" -> a Key."""
    minor = text.endswith("m")
    name = text[:-1] if minor else text
    return Key(NAMES.index(name) if name in NAMES else NAMES.index(FLATS.get(name, name)), minor)


FLATS = {"Db": "C#", "D#": "Eb", "Gb": "F#", "G#": "Ab", "A#": "Bb"}


def load_style(path: Path) -> Style:
    """A style from its JSON file (styles/<name>.json)."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return Style(
        name=Path(path).stem, tempo=int(d["tempo"]), key=parse_key(d["key"]), progression=list(d["progression"]),
        programs={k: int(v) for k, v in d["programs"].items()}, band=list(d["band"]), swing=bool(d.get("swing")),
        drums=[(float(b), DRUMS[k] if isinstance(k, str) else int(k), int(v)) for k, b, v in d.get("drums", [])],
        bass=d.get("bass", "roots"), comp={p: [(float(b), float(n)) for b, n in hits] for p, hits in d.get("comp", {}).items()})


def load_styles(folder: Path = STYLE_DIR) -> dict:
    return {p.stem: load_style(p) for p in sorted(Path(folder).glob("*.json"))}


STYLES = load_styles()
DEFAULT = "swing"


def _swing(beat: float) -> float:
    """Shuffle: an off-beat eighth comes a triplet later."""
    return beat + 1 / 6 if abs(beat % 1 - 0.5) < 1e-6 else beat


@dataclass
class BarContext:
    chord: Chord
    next_chord: Chord
    key: Key
    bar: int                 # bars since the jam began
    last_of_phrase: bool     # the last bar of the progression (a fill goes here)
    entering: set            # parts that come in on this bar
    memory: dict             # per part, from bar to bar (voicings)


def bar_notes(style: Style, part: str, ctx: BarContext) -> list:
    """One bar of `part` in `style`: ["note", beat, channel, pitch, velocity, beats]."""
    ch = CHANNEL[part]
    out = []

    def note(beat, pitch, vel, beats):
        if 0 <= pitch < 128:
            out.append(["note", beat, ch, int(pitch), int(max(1, min(127, vel))), beats])

    c, nxt = ctx.chord, ctx.next_chord
    if part == "drums":
        for beat, key, vel in style.drums:
            if ctx.last_of_phrase and beat >= 3 and key in (SNARE, RIM, CLAP):
                continue
            note(beat, key, vel, 0.2)
        if ctx.last_of_phrase:                       # a fill into the next round
            for k in range(4):
                note(3 + k / 4, SNARE if k % 2 == 0 else TOM, 74 + 10 * k, 0.15)
        if ctx.bar % len(style.progression) == 0 and ctx.bar > 0 or "drums" in ctx.entering:
            note(0, CRASH, 104, 1.5)
    elif part == "bass":
        r = note_in(c.root, 33)
        third = r + (3 if c.minor else 4)
        fifth = r + 7
        seventh = r + (10 if c.quality in ("7", "m7", "min") else 11)
        n = note_in(nxt.root, 33)
        approach = n - 1 if n - 1 != fifth else n + 1
        kind = style.bass
        if kind == "walking":
            line = [r, third, fifth, approach] if ctx.bar % 2 == 0 else [r, r + 2, third, approach]
            for k, p in enumerate(line):
                note(k, p, 96 if k % 2 == 0 else 84, 0.9)
        elif kind == "boogie":
            for k, p in enumerate([r, third, fifth, r + 9, seventh, r + 9, fifth, third]):
                note(k / 2, p, 100 if k % 2 == 0 else 82, 0.42)
        elif kind == "eighths":
            for k in range(8):
                note(k / 2, r + (12 if k == 7 else 0), 100 if k % 2 == 0 else 86, 0.42)
        elif kind == "octaves":
            for k in range(8):
                note(k / 2, r + (12 if k % 2 else 0), 104 if k % 2 == 0 else 90, 0.4)
        elif kind == "funk":
            for beat, p, vel in ((0, r, 112), (0.75, r + 12, 90), (1.5, seventh, 92), (2.5, r, 108),
                                 (2.75, r, 80), (3.25, fifth, 94), (3.5, r + 12, 88)):
                note(beat, p, vel, 0.22)
        elif kind == "onedrop":
            for beat, p, d in ((0, r, 0.9), (1.5, fifth, 0.4), (2.0, fifth, 0.4), (2.5, r + 12, 0.4), (3.5, third, 0.4)):
                note(beat, p, 104, d)
        elif kind == "bossa":
            for beat, p, d in ((0, r, 1.4), (1.5, fifth - 12 if fifth > 45 else fifth, 0.45),
                               (2, fifth - 12 if fifth > 45 else fifth, 1.4), (3.5, r, 0.45)):
                note(beat, p, 92, d)
        elif kind == "tango":
            for beat, p, vel in ((0, r, 108), (1, r, 82), (2, fifth, 100), (3, r, 82)):
                note(beat, p, vel, 0.42)
            note(1.75, r + 6, 70, 0.2)                     # the drag into 3
        else:
            note(0, r, 100, 1.9)
            note(2, r, 92, 1.9)
    elif part in ("piano", "guitar", "organ", "bandoneon"):
        low = {"piano": 57, "guitar": 52, "organ": 55, "bandoneon": 57}[part]
        v = voicing(c, low, ctx.memory.get(part))
        ctx.memory[part] = v
        if part == "guitar" and style.name == "rock":
            v = [note_in(c.root, 40), note_in(c.root, 40) + 7, note_in(c.root, 40) + 12]    # power chord
        hits = style.comp.get(part, [(0, 3.9)])
        if style.name == "tango" and part == "bandoneon" and ctx.bar % 2 == 1:
            hits = [(0, 0.45), (1.5, 0.45), (3, 0.45)]                            # sincopa: 3-3-2
        for k, (beat, beats) in enumerate(hits):
            vel = (96 if beat in (0, 2) else 80) if part != "organ" else 60
            for p in v:
                note(beat, p, vel - (6 if part == "guitar" else 0), beats)
    elif part == "strings":
        for p in voicing(c, 62, ctx.memory.get(part)):
            note(0, p, 52 if ctx.bar % 4 else 60, 3.95)
        ctx.memory[part] = voicing(c, 62, ctx.memory.get(part))
    elif part == "sax":
        tones = c.tones()
        line = [note_in(tones[1], 60), note_in(tones[-1], 60)]            # the third, then the seventh
        if style.swing:
            note(0, line[0], 70, 1.9)
            note(2, line[1], 66, 1.9)
        else:
            note(0, line[0], 64, 3.9)
    elif part == "brass":
        v = voicing(c, 62)
        if ctx.bar % 2 == 1 or "brass" in ctx.entering:
            hits = [(0, 0.6)] if "brass" in ctx.entering else [(2.5, 0.3), (3.5, 0.3)]
            if style.name in ("funk", "disco"):
                hits = [(1.5, 0.2), (3.5, 0.2)] if not "brass" in ctx.entering else [(0, 0.5)]
            for beat, beats in hits:
                for p in v + [v[0] + 12]:
                    note(beat, p, 108 if beat == 0 else 92, beats)
    if style.swing:
        for e in out:
            e[1] = _swing(e[1])
    return out


def programs(style: Style) -> list:
    """The program changes for every part's channel."""
    return [["program", 0, CHANNEL[p], style.programs[p]] for p in PARTS if p != "drums" and p in style.programs]
