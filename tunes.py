"""Melodies everybody knows, to jam over: "a reggae over Frère Jacques".

Only tunes that are free to use: traditional songs and nursery rhymes, and
themes by composers who died long ago. A tune has its key (and, where the usual chords
differ from what fit_chords would pick, its chords as degrees), and its notes
written as
NOTE[:beats] ("E4", "D#5:.5", "r:1" a rest; a beat if no length), bars
between "|" - four beats each, which the tests check. Its names are what
people call it in the twelve languages; any of them finds it, in any
language ("say" has the one to say, per language, when it isn't the first).
A new file is a new tune.

When ovos-skill-karaoke is installed, the melodies of its songbook come
too: "a tango over Hey Emkay".
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from . import melody as M
from .melody import Melody
from .music import NAMES, Key

NOTE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d)$")
PC = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}

TUNE_DIR = Path(__file__).resolve().parent / "tunes"
#: tunes longer than this are cut (their first bars): a jam goes round them
LONGEST = 16


def load_tune(path: Path) -> dict:
    """A tune from its JSON file: {"names", "key", "notes", ["chords"], ["say"]}."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(d.get("notes"), list):
        d["notes"] = " | ".join(d["notes"])
    return d


def load_tunes(folder: Path = TUNE_DIR) -> dict:
    return {p.stem: load_tune(p) for p in sorted(Path(folder).glob("*.json"))}


TUNES = load_tunes()


def songbook() -> dict:
    """ovos-skill-karaoke's songs, when it is installed: their melodies, to
    jam over ("a tango over Hey Emkay"). Songs in 4/4 (or 2/4, 2/2) only;
    the jam's bars are four beats."""
    if _SONGBOOK:
        return _SONGBOOK[0]
    found = {}
    try:
        import importlib.util
        spec = importlib.util.find_spec("ovos_skill_karaoke")
        folder = Path(spec.origin).parent / "songs" if spec and spec.origin else None
        if folder and folder.is_dir():
            for path in sorted(folder.glob("*.kar")):
                if "." in path.stem or path.stem in TUNES:      # a translation, or one we have
                    continue
                try:
                    tune = _from_kar(path)
                except Exception:
                    tune = None
                if tune:
                    found[path.stem] = tune
    except Exception:
        pass
    _SONGBOOK.append(found)
    return found


_SONGBOOK: list = []


def _from_kar(path: Path) -> dict | None:
    import mido
    from ovos_skill_karaoke import song as karaoke
    data = path.read_bytes()
    s = karaoke.load(data)
    mid = s.midi
    if s.melody_track is None:
        return None
    for track in mid.tracks:
        for m in track:
            if m.type == "time_signature" and (m.numerator * 4 // m.denominator) not in (2, 4):
                return None
    tpb = mid.ticks_per_beat
    on, notes, tick = {}, [], 0
    for m in mid.tracks[s.melody_track]:
        tick += m.time
        if m.type == "note_on" and m.velocity > 0:
            on[m.note] = tick
        elif m.type in ("note_off", "note_on") and m.note in on:
            start = on.pop(m.note)
            notes.append((start / tpb, m.note, (tick - start) / tpb))
    if len(notes) < 4:
        return None
    notes.sort()
    first_bar = int(notes[0][0] // 4)
    notes = [(b - 4 * first_bar, p, d) for b, p, d in notes if b - 4 * first_bar < 4 * LONGEST]
    title = s.title or path.stem.replace("_", " ").title()
    names = [title, path.stem.replace("_", " ")]
    key = M.key_of(notes)
    return {"names": names, "key": key.name, "melody": notes, "songbook": True}


def normal(text: str) -> str:
    s = unicodedata.normalize("NFKD", text.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def pitch(token: str) -> int:
    m = NOTE.match(token)
    if not m:
        raise ValueError(f"not a note: {token}")
    letter, acc, octave = m.groups()
    return 12 * (int(octave) + 1) + PC[letter.lower()] + {"#": 1, "b": -1, "": 0}[acc]


def bars(notes: str) -> list[list]:
    """The tune as bars of (pitch or None, beats)."""
    out = []
    for bar in notes.split("|"):
        row = []
        for tok in bar.split():
            name, _, beats = tok.partition(":")
            row.append((None if name == "r" else pitch(name), float(beats) if beats else 1.0))
        out.append(row)
    return out


def melody(tune_id: str) -> Melody:
    t = every()[tune_id]
    if "melody" in t:                                   # from the songbook: (beat, pitch, beats)
        notes = [(b, p, d * 0.95) for b, p, d in t["melody"]]
        end = max(b + d for b, _, d in t["melody"])
        return Melody(notes, max(1, min(LONGEST, -(-int(end) // 4))))
    notes, beat = [], 0.0
    for bar in bars(t["notes"]):
        for p, d in bar:
            if p is not None:
                notes.append((beat, p, d * 0.95))
            beat += d
    return Melody(notes, max(1, round(beat / 4)))


def every() -> dict:
    """The library's tunes and the karaoke songbook's."""
    return {**songbook(), **TUNES}


def key(tune_id: str) -> Key:
    k = every()[tune_id]["key"]
    minor = k.endswith("m")
    return Key(NAMES.index(k[:-1] if minor else k), minor)


def find(utterance: str) -> str | None:
    """The tune named in `utterance` (the longest name that is in it)."""
    u = f" {normal(utterance)} "
    best, length = None, 0
    for tid, t in every().items():
        for name in t["names"]:
            n = normal(name)
            if len(n) > length and f" {n} " in u:
                best, length = tid, len(n)
    return best


def title(tune_id: str, lang: str = "en") -> str:
    """The tune's name to say in `lang`."""
    t = every()[tune_id]
    return (t.get("say") or {}).get(lang.split("-")[0].lower()) or t["names"][0]
