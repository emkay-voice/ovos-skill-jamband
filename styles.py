"""The band's styles: what each part plays, a bar at a time.

A part's bar is a list of notes ["note", beat, channel, pitch, velocity,
beats]; the jam turns beats into seconds and sends them. Each style has its
groove for every part, so "add the bass" in a swing gets a walking bass, in
reggae a one-drop bass, in disco octaves.

Parts: drums, bass, piano, guitar, organ, strings, brass, sax, bandoneon.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .music import Chord, Key, note_in, voicing

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


def _hats(vel=(78, 56)):
    return [(b / 2, HAT, vel[b % 2]) for b in range(8)]


STYLES = {
    "swing": Style(
        "swing", 140, Key(5), ["I6", "vi7", "ii7", "V7"],
        {"bass": 32, "piano": 0, "guitar": 26, "organ": 16, "strings": 48, "brass": 61, "sax": 66,
         "bandoneon": 23},
        ["drums", "bass", "piano", "brass", "sax"], swing=True,
        drums=[(b, RIDE, 104 if b % 2 else 92) for b in range(4)] + [(1.5, RIDE, 80), (3.5, RIDE, 80)]
        + [(1, PEDAL, 92), (3, PEDAL, 92)] + [(b, KICK, 50) for b in range(4)] + [(3.5, SNARE, 50)],
        bass="walking",
        comp={"piano": [(0, 0.4), (1.5, 0.35)], "guitar": [(b, 0.4) for b in range(4)],
              "organ": [(0, 3.9)], "bandoneon": [(0, 3.9)]}),
    "blues": Style(
        "blues", 92, Key(4), ["I7", "IV7", "I7", "I7", "IV7", "IV7", "I7", "I7", "V7", "IV7", "I7", "V7"],
        {"bass": 33, "piano": 0, "guitar": 27, "organ": 17, "strings": 48, "brass": 61, "sax": 66,
         "bandoneon": 23},
        ["drums", "bass", "piano", "guitar", "organ"], swing=True,
        drums=[(b / 2, HAT, 84 if b % 2 == 0 else 62) for b in range(8)]
        + [(0, KICK, 104), (2, KICK, 96), (2.5, KICK, 70), (1, SNARE, 100), (3, SNARE, 100)],
        bass="boogie",
        comp={"piano": [(0.5, 0.3), (1.5, 0.3), (2.5, 0.3), (3.5, 0.3)],
              "guitar": [(1, 0.35), (3, 0.35)], "organ": [(0, 3.9)], "bandoneon": [(0, 3.9)]}),
    "rock": Style(
        "rock", 120, Key(9), ["I", "V", "vi", "IV"],
        {"bass": 33, "piano": 0, "guitar": 29, "organ": 18, "strings": 48, "brass": 61, "sax": 66,
         "bandoneon": 23},
        ["drums", "bass", "guitar", "piano", "organ"],
        drums=_hats() + [(0, KICK, 112), (2, KICK, 108), (2.5, KICK, 84), (1, SNARE, 112), (3, SNARE, 112)],
        bass="eighths",
        comp={"piano": [(0, 1.9), (2, 1.9)], "guitar": [(b / 2, 0.45) for b in range(8)],
              "organ": [(0, 3.9)], "bandoneon": [(0, 3.9)]}),
    "pop": Style(
        "pop", 104, Key(0), ["I", "V", "vi", "IV"],
        {"bass": 33, "piano": 0, "guitar": 25, "organ": 16, "strings": 48, "brass": 61, "sax": 65,
         "bandoneon": 23},
        ["drums", "bass", "piano", "guitar", "strings"],
        drums=_hats((70, 50)) + [(0, KICK, 108), (1.5, KICK, 84), (2, KICK, 104), (1, SNARE, 104), (3, SNARE, 104)],
        bass="eighths",
        comp={"piano": [(b, 0.9) for b in range(4)], "guitar": [(0, 0.4), (1.5, 0.4), (2, 0.4), (3, 0.4), (3.5, 0.4)],
              "organ": [(0, 3.9)], "bandoneon": [(0, 3.9)]}),
    "funk": Style(
        "funk", 104, Key(4, True), ["i7", "i7", "IV7", "i7"],
        {"bass": 36, "piano": 4, "guitar": 28, "organ": 17, "strings": 48, "brass": 61, "sax": 66,
         "bandoneon": 23},
        ["drums", "bass", "guitar", "piano", "brass"],
        drums=[(b / 4, HAT, 80 if b % 2 == 0 else 52) for b in range(16)]
        + [(0, KICK, 116), (0.75, KICK, 92), (2.5, KICK, 108), (1, SNARE, 112), (3, SNARE, 112),
           (1.75, SNARE, 44), (3.25, SNARE, 44)],
        bass="funk",
        comp={"piano": [(0.5, 0.2), (1.75, 0.2), (2.5, 0.2), (3.75, 0.2)],
              "guitar": [(b / 4, 0.12) for b in (1, 2, 5, 6, 9, 10, 13, 14)],
              "organ": [(0, 3.9)], "bandoneon": [(0, 3.9)]}),
    "disco": Style(
        "disco", 120, Key(9, True), ["i7", "i7", "iv7", "v7"],
        {"bass": 38, "piano": 4, "guitar": 28, "organ": 16, "strings": 48, "brass": 62, "sax": 65,
         "bandoneon": 23},
        ["drums", "bass", "strings", "guitar", "brass"],
        drums=[(b, KICK, 112) for b in range(4)] + [(b + 0.5, OPEN, 78) for b in range(4)]
        + [(b / 4, HAT, 44) for b in range(16)] + [(1, CLAP, 96), (3, CLAP, 96)],
        bass="octaves",
        comp={"piano": [(b + 0.5, 0.3) for b in range(4)], "guitar": [(b / 4, 0.1) for b in range(1, 16, 2)],
              "organ": [(0, 3.9)], "bandoneon": [(0, 3.9)]}),
    "reggae": Style(
        "reggae", 76, Key(7), ["I", "IV", "I", "V"],
        {"bass": 33, "piano": 0, "guitar": 27, "organ": 16, "strings": 48, "brass": 61, "sax": 66,
         "bandoneon": 23},
        ["drums", "bass", "guitar", "organ"],
        drums=_hats((66, 46)) + [(2, KICK, 108), (2, RIM, 92)],
        bass="onedrop",
        comp={"piano": [(1, 0.2), (3, 0.2)], "guitar": [(1, 0.18), (3, 0.18)],
              "organ": [(b + 0.5, 0.22) for b in range(4)], "bandoneon": [(0, 3.9)]}),
    "bossa": Style(
        "bossa", 128, Key(0), ["Imaj7", "Imaj7", "ii7", "V7"],
        {"bass": 32, "piano": 4, "guitar": 24, "organ": 16, "strings": 48, "brass": 61, "sax": 66,
         "bandoneon": 23},
        ["drums", "bass", "guitar", "piano", "sax"],
        drums=[(b / 2, HAT, 52) for b in range(8)] + [(0, KICK, 88), (1.5, KICK, 76), (2, KICK, 88), (3.5, KICK, 76)]
        + [(0, RIM, 76), (0.75, RIM, 70), (1.5, RIM, 72), (2.5, RIM, 76), (3.25, RIM, 70)],
        bass="bossa",
        comp={"piano": [(0, 1.4), (1.5, 0.9), (3, 0.9)], "guitar": [(0, 0.7), (0.75, 0.6), (1.5, 0.9), (2.5, 0.7), (3.25, 0.6)],
              "organ": [(0, 3.9)], "bandoneon": [(0, 3.9)]}),
    "tango": Style(
        "tango", 112, Key(2, True), ["i", "V7", "V7", "i", "iv", "i", "V7", "i"],
        {"bass": 32, "piano": 0, "guitar": 24, "organ": 16, "strings": 48, "brass": 61, "sax": 66,
         "bandoneon": 23},
        ["bandoneon", "bass", "piano", "strings"],
        drums=[(0, KICK, 96), (1.5, KICK, 70), (2, KICK, 90), (1, SNARE, 60), (3, SNARE, 66)],
        bass="tango",
        comp={"bandoneon": [(b, 0.32) for b in range(4)], "piano": [(0, 0.3), (2, 0.3)],
              "guitar": [(0, 0.45), (1.5, 0.45), (3, 0.45)], "organ": [(0, 3.9)]}),
}
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
