"""Solos: an instrument improvises over the chords for a round.

The line is made a bar at a time from the style's scale (the blues scale in
a blues, a pentatonic in pop, harmonic minor in a tango), with chord notes
on the strong beats, rhythms that suit the style, phrases that breathe, and
a last note on the chord's root. It is drawn from a seed, so a saved jam
plays the same solo again.
"""
from __future__ import annotations

import random

from .music import note_in

#: the scale a style solos in: semitones above the key's tonic
SCALES = {
    "blues": (0, 3, 5, 6, 7, 10),                # minor blues scale, over major chords too
    "minor_pent": (0, 3, 5, 7, 10),
    "major_pent": (0, 2, 4, 7, 9),
    "major": (0, 2, 4, 5, 7, 9, 11),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "harmonic": (0, 2, 3, 5, 7, 8, 11),
}
STYLE_SCALE = {"blues": "blues", "swing": "major", "rock": "blues", "funk": "dorian", "disco": "minor_pent",
               "pop": "major_pent", "reggae": "major_pent", "bossa": "major", "tango": "harmonic"}
#: one bar's rhythms: (beat, beats); None is a breath
RHYTHMS = {
    "swing": [[(0, .5), (.5, .5), (1, .5), (1.5, .5), (2, 1), (3, .5), (3.5, .5)],
              [(0, 1.5), (1.5, .5), (2, .5), (2.5, .5), (3, 1)],
              [(.5, .5), (1, .5), (1.5, .5), (2, .5), (2.5, 1.5)],
              [(0, .5), (.5, .5), (1, .5), (1.5, .5), (2, .5), (2.5, .5), (3, .5), (3.5, .5)]],
    "straight": [[(0, 1), (1, .5), (1.5, .5), (2, 2)],
                 [(0, .5), (.5, .5), (1, 1), (2, .5), (2.5, .5), (3, 1)],
                 [(.5, .5), (1, .5), (1.5, 1), (2.5, .5), (3, 1)],
                 [(0, 2), (2, .5), (2.5, .5), (3, 1)]],
    "funk": [[(0, .25), (.5, .25), (.75, .5), (1.5, .25), (2, .5), (2.75, .25), (3, .5)],
             [(0, .5), (.75, .25), (1, .25), (1.25, .5), (2.5, .25), (2.75, .25), (3, 1)]],
    "tango": [[(0, .75), (.75, .75), (1.5, .5), (2, 1), (3, .5), (3.5, .5)],
              [(0, .5), (.5, .25), (.75, .25), (1, 1), (2, .5), (2.5, .5), (3, 1)]],
}
RANGES = {"sax": (58, 80), "brass": (60, 82), "guitar": (55, 79), "piano": (62, 86), "organ": (60, 84),
          "strings": (64, 88), "bandoneon": (60, 84), "bass": (31, 55), "lead": (60, 84)}


def rhythms(style) -> list:
    if style.name == "funk":
        return RHYTHMS["funk"]
    if style.name == "tango":
        return RHYTHMS["tango"]
    return RHYTHMS["swing" if style.swing else "straight"]


def solo_bar(style, part: str, ctx, channel: int, seed: int, bar_of_solo: int, bars: int) -> list:
    """One bar of `part`'s solo: jam notes ["note", beat, channel, pitch, vel, beats].
    `bar_of_solo` counts from 0; the solo lasts `bars`."""
    rng = random.Random(seed * 1009 + bar_of_solo * 7919 + ctx.bar)
    low, high = RANGES.get(part, (60, 84))
    scale = SCALES[STYLE_SCALE.get(style.name, "major")]
    tonic = ctx.key.tonic
    pcs = sorted({(tonic + s) % 12 for s in scale} | set(ctx.chord.tones()))
    pool = [p for p in range(low, high + 1) if p % 12 in pcs]
    chord = set(ctx.chord.tones())
    mem = ctx.memory.setdefault(f"solo_{part}", {"last": (low + high) // 2, "dir": 1})
    last = bar_of_solo == bars - 1
    first = bar_of_solo == 0
    pattern = list(rng.choice(rhythms(style)))
    if last:                                   # land: a short run to the root
        pattern = [(b, d) for b, d in pattern if b < 2] + [(2, 2)]
    elif bar_of_solo % 2 == 1 and rng.random() < 0.45:
        pattern = [(b, d) for b, d in pattern if b < 2.5]          # a breath at the end of a phrase
    out = []
    for k, (beat, beats) in enumerate(pattern):
        strong = beat in (0, 2) or beats >= 1
        step = mem["dir"] * rng.choice((1, 1, 1, 2, 2, 3))
        if rng.random() < 0.18:
            mem["dir"] = -mem["dir"]
        i = min(range(len(pool)), key=lambda j: abs(pool[j] - mem["last"]))
        i = max(0, min(len(pool) - 1, i + step))
        p = pool[i]
        if p <= low + 2 or p >= high - 2:
            mem["dir"] = 1 if p <= low + 2 else -1
        if strong:                              # chord notes where it is heard
            near = [q for q in pool if q % 12 in chord and abs(q - p) <= 3]
            if near:
                p = min(near, key=lambda q: abs(q - p))
        if last and k == len(pattern) - 1:
            p = note_in(ctx.chord.root, (low + high) // 2 - 6)
        vel = 100 if strong else 84
        if first and k == 0:
            vel = 108
        out.append(["note", beat, channel, p, vel + rng.randint(-6, 6), beats * 0.9])
        mem["last"] = p
    return out


def drum_solo_bar(ctx, seed: int, bar_of_solo: int, bars: int) -> list:
    """The drummer's turn: toms and snare around a steady kick."""
    rng = random.Random(seed * 31 + bar_of_solo)
    toms = (50, 48, 47, 45, 43, 41)
    out = [["note", b, 9, 36, 110, 0.2] for b in (0, 2)]
    hits = 16 if bar_of_solo == bars - 1 else rng.choice((8, 12, 16))
    for k in range(hits):
        beat = k * 4 / hits
        key = rng.choice(toms + (38, 38)) if rng.random() < 0.85 else 42
        out.append(["note", beat, 9, key, 80 + rng.randint(0, 30), 0.15])
    if bar_of_solo == bars - 1:
        out.append(["note", 3.75, 9, 49, 118, 1.0])
    return out
