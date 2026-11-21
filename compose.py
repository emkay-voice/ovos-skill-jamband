"""Emkay's own jam: a tune from the library, a style, and a whole
arrangement - intro, the tune, solos, a break, maybe a key change for the
last time through, and the ending - written as a saved jam's log, so it
plays like one: say something and it is yours to change; save it after.
"""
from __future__ import annotations

import random

from . import melody as M
from . import tunes as T
from .jam import SOLO_BARS, State, encode_change
from .styles import STYLES

#: a solo in this style is played by one of these
SOLOISTS = {"swing": ["sax", "brass", "piano"], "blues": ["guitar", "organ", "sax", "piano"],
            "rock": ["guitar", "organ"], "pop": ["piano", "guitar", "strings"], "funk": ["sax", "brass", "guitar"],
            "disco": ["brass", "strings", "guitar"], "reggae": ["organ", "guitar"], "bossa": ["sax", "guitar", "piano"],
            "tango": ["bandoneon", "strings", "piano"]}
LEADS = {"swing": "sax", "blues": "sax", "rock": "guitar", "pop": "piano", "funk": "sax", "disco": "brass",
         "reggae": "organ", "bossa": "sax", "tango": "bandoneon"}


def chords_for(tune_id: str, mel: M.Melody, key, style_name: str) -> list:
    t = T.every()[tune_id]
    degrees = t.get("chords") if style_name != "blues" else None
    if style_name == "blues" and t.get("chords"):
        degrees = [d if d.endswith("7") else d + "7" for d in t["chords"]]
    return [key.chord(d) for d in (degrees or M.fit_chords(mel, key, style_name))]


def compose(rng: random.Random | None = None, tune_id: str | None = None, style_name: str | None = None) -> dict:
    """A whole jam, as a recording: {"first", "log", "bars", "tune", "style"}."""
    rng = rng or random.Random()
    tune_id = tune_id or rng.choice(list(T.every()))
    style_name = style_name or rng.choice(list(STYLES))
    style = STYLES[style_name]
    mel = T.melody(tune_id)
    key = T.key(tune_id)
    chords = chords_for(tune_id, mel, key, style_name)
    L = len(chords)
    st = State(style=style, key=key, tempo=style.tempo, parts=[], chords=chords, melody=mel,
               lead=LEADS[style_name], seed=rng.randrange(1, 1 << 30), key_chosen=True)
    log = []

    def at(bar, what, args=None):
        log.append({"bar": bar, "do": what, "args": args or {}})

    band = list(style.band)
    # the intro: the first part alone, the rest coming in a bar apart
    at(0, "change", {"parts": band[:1]})
    at(0, "intro")
    k = min(4, L)
    for i, part in enumerate(band[1:], 1):
        at(min(i, k - 1), "change", {"parts": band[:i + 1]})
    bar = k
    # the tune, once (twice when it is short)
    heads = 2 if L <= 4 else 1
    bar += heads * L
    # solos: one or two, a round each (at most SOLO_BARS), from the top of the chords
    soloists = [p for p in SOLOISTS[style_name] if p != st.lead] or SOLOISTS[style_name]
    rng.shuffle(soloists)
    count = 2 if L <= 8 and len(soloists) > 1 else 1
    for part in soloists[:count]:
        at(bar, "top")
        bars = min(L, SOLO_BARS)
        at(bar, "solo", {"part": part, "bars": bars})
        bar += bars
    if "drums" in band and rng.random() < 0.4:          # the drummer's turn: four bars
        at(bar, "top")
        at(bar, "solo", {"part": "drums", "bars": 4})
        bar += 4
    # the tune again: a break on its first bar, maybe a key up
    at(bar, "top")
    if rng.random() < 0.5:
        up = key.__class__((key.tonic + rng.choice((1, 2))) % 12, key.minor)
        semis = (up.tonic - key.tonic) % 12
        at(bar, "change", encode_change({"key": up, "melody": mel.transposed(semis),
                                          "chords": chords_for(tune_id, mel.transposed(semis), up, style_name)}))
    at(bar, "break")
    bar += L
    at(bar, "finish")
    return {"first": st.to_dict(), "log": log, "bars": bar + 1, "tune": tune_id, "style": style_name,
            "soloists": soloists[:count]}
