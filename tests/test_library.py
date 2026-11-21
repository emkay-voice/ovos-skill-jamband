"""The data files: every tune, style and bundled jam must load and add up."""
import json

import pytest

from ovos_skill_jamband import tunes as T
from ovos_skill_jamband.jam import render
from ovos_skill_jamband.jams import Jams, midi_bytes
from ovos_skill_jamband.music import DEGREES
from ovos_skill_jamband.styles import BASSES, CHANNEL, STYLES

from conftest import ROOT

LANGS = ["en", "da", "de", "nl", "es", "fr", "it", "pt", "ca", "gl", "eu"]


@pytest.mark.parametrize("tid", sorted(T.TUNES))
def test_every_tune_adds_up(tid):
    t = T.TUNES[tid]
    for i, bar in enumerate(T.bars(t["notes"])):
        assert abs(sum(d for _, d in bar) - 4) < 1e-9, (tid, i + 1)
    assert t["names"] and T.key(tid)
    for d in t.get("chords", []):
        assert d in DEGREES
    if "chords" in t:
        assert len(t["chords"]) == T.melody(tid).bars
    m = T.melody(tid)
    assert all(40 <= p <= 90 for p in m.pitches())
    for lang in LANGS:
        assert T.title(tid, lang)


def test_a_name_finds_its_tune_in_any_language():
    assert T.find("jam a reggae over Frère Jacques") == "frere_jacques"
    assert T.find("spil mester jakob som tango") == "frere_jacques"
    assert T.find("une bossa sur l'hymne à la joie") == "ode_to_joy"
    assert T.find("the weather tomorrow") is None


@pytest.mark.parametrize("name", sorted(STYLES))
def test_every_style_file(name):
    s = STYLES[name]
    assert s.bass in BASSES and s.band and set(s.band) <= set(CHANNEL)
    assert set(s.programs) >= {p for p in CHANNEL if p != "drums"}
    for d in s.progression:
        assert d in DEGREES
    for beat, key, vel in s.drums:
        assert 0 <= beat < 4 and 35 <= key <= 81 and 0 < vel <= 127
    for locale in (ROOT / "locale").iterdir():
        assert (locale / f"{name}.voc").exists(), (name, locale.name)


def test_the_bundled_jams_play_to_their_end():
    jams = Jams(ROOT / "nowhere", ROOT / "jams").all()
    assert len(jams) >= 5 and all(j["bundled"] for j in jams)
    for j in jams:
        assert set(j["names"]) >= set(LANGS)
        bars = render(j)
        assert bars[-1][2] and len(bars) <= j["bars"] + 1          # it ends: the last chord
        assert midi_bytes(j).startswith(b"MThd")


def test_locales_have_the_same_files():
    folders = list((ROOT / "locale").iterdir())
    names = {f.name for f in folders[0].iterdir()}
    for folder in folders:
        assert {f.name for f in folder.iterdir()} == names, folder.name
        meta = json.loads((folder / "skill.json").read_text(encoding="utf-8"))
        assert meta["examples"] and meta["description"]
