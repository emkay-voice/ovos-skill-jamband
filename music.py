"""Keys, chords and progressions.

A chord is (root pitch class, quality): quality is "maj", "min", "7",
"maj7", "m7". A progression is chords by the bar, as degrees of the key
(I, IV, V7, vi ...), so a style's progression plays in any key.
"""
from __future__ import annotations

from dataclasses import dataclass

NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
INTERVALS = {"maj": (0, 4, 7), "min": (0, 3, 7), "7": (0, 4, 7, 10),
             "maj7": (0, 4, 7, 11), "m7": (0, 3, 7, 10), "6": (0, 4, 7, 9)}
#: degrees as Roman numerals: (semitones above the key, quality)
DEGREES = {
    "I": (0, "maj"), "I7": (0, "7"), "Imaj7": (0, "maj7"), "I6": (0, "6"),
    "i": (0, "min"), "i7": (0, "m7"),
    "ii": (2, "min"), "ii7": (2, "m7"), "II7": (2, "7"),
    "iii": (4, "min"), "iii7": (4, "m7"),
    "IV": (5, "maj"), "IV7": (5, "7"), "iv": (5, "min"), "iv7": (5, "m7"),
    "V": (7, "maj"), "V7": (7, "7"), "v": (7, "min"), "v7": (7, "m7"),
    "VI": (8, "maj"), "vi": (9, "min"), "vi7": (9, "m7"), "VI7": (9, "7"),
    "bVI": (8, "maj"), "bVII": (10, "maj"), "VII": (10, "maj"),
}


@dataclass(frozen=True)
class Chord:
    root: int        # pitch class 0-11
    quality: str = "maj"

    @property
    def name(self) -> str:
        suffix = {"maj": "", "min": "m", "7": "7", "maj7": "maj7", "m7": "m7", "6": "6"}[self.quality]
        return NAMES[self.root] + suffix

    @property
    def minor(self) -> bool:
        return self.quality in ("min", "m7")

    def tones(self) -> list[int]:
        """Pitch classes, root first."""
        return [(self.root + i) % 12 for i in INTERVALS[self.quality]]


@dataclass(frozen=True)
class Key:
    tonic: int       # pitch class
    minor: bool = False

    @property
    def name(self) -> str:
        return NAMES[self.tonic] + ("m" if self.minor else "")

    def chord(self, degree: str) -> Chord:
        semis, quality = DEGREES[degree]
        return Chord((self.tonic + semis) % 12, quality)

    def scale(self) -> list[int]:
        steps = (0, 2, 3, 5, 7, 8, 10) if self.minor else (0, 2, 4, 5, 7, 9, 11)
        return [(self.tonic + s) % 12 for s in steps]


def note_in(pc: int, low: int) -> int:
    """The MIDI note of pitch class `pc` at or above `low`."""
    return low + (pc - low) % 12


def voicing(chord: Chord, low: int = 55, previous: list[int] | None = None) -> list[int]:
    """Close position from `low`, or the inversion nearest the previous
    voicing (so the chords move smoothly, as a pianist plays them)."""
    tones = chord.tones()
    base = sorted(note_in(pc, low) for pc in tones)
    if not previous:
        return base
    centre = sum(previous) / len(previous)
    options = []
    for k in range(len(base)):
        inv = sorted(base[k:] + [n + 12 for n in base[:k]])
        for shift in (-12, 0, 12):
            v = [n + shift for n in inv]
            if v[0] >= low - 5 and v[-1] <= low + 21:
                options.append(v)
    return min(options or [base], key=lambda v: abs(sum(v) / len(v) - centre))
