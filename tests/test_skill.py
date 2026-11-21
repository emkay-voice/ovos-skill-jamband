import time
from unittest.mock import MagicMock

import pytest
from ovos_bus_client.message import Message

import ovos_skill_jamband as sk

from conftest import ROOT


@pytest.fixture
def skill(monkeypatch, tmp_path):
    monkeypatch.setattr(sk.OVOSSkill, "__init__", lambda self, *a, **k: None)
    monkeypatch.setattr(sk.ConversationalSkill, "__init__", lambda self, *a, **k: None)
    monkeypatch.setattr(sk.JamBandSkill, "activate", lambda self, *a, **k: None, raising=False)
    s = sk.JamBandSkill()
    s.skill_id = "ovos-skill-jamband.test"
    monkeypatch.setattr(sk.JamBandSkill, "lang", "en-US", raising=False)
    bus = MagicMock()
    bus.band = {"engine": "builtin", "latency": 0.05, "clips": True}
    bus.wait_for_response.side_effect = lambda msg, reply, timeout=None: Message(reply, bus.band) if bus.band else None
    monkeypatch.setattr(sk.JamBandSkill, "bus", bus, raising=False)
    monkeypatch.setattr(sk.JamBandSkill, "gui", MagicMock(), raising=False)
    monkeypatch.setattr(sk.JamBandSkill, "dialog_renderer", MagicMock(render=lambda n, d: n[5:]), raising=False)
    s.speak_dialog = MagicMock()
    s.file_system = MagicMock(path=str(tmp_path))
    yield s
    s.stop()


def said(skill):
    return [c[0][0] for c in skill.speak_dialog.call_args_list]


def sent(skill, t):
    return [c[0][0].data for c in skill.bus.emit.call_args_list if c[0][0].msg_type == t]


def test_lets_jam_then_drums_then_bass_then_everyone(skill):
    skill.handle_jam(MagicMock(data={"utterance": "let's jam a blues in E"}))
    name, data = skill.speak_dialog.call_args[0]
    assert name == "start" and data == {"style": "blues", "key": "E major"}
    assert skill.speak_dialog.call_args[1]["expect_response"]
    for words, comment in (("drums", "in_drums"), ("and now a bass", "in_bass"), ("the whole band", "in_band")):
        assert skill.converse(Message("", {"utterances": [words]}))
        assert said(skill)[-1] == comment
    assert set(skill.jam.state.parts) >= {"drums", "bass", "piano", "guitar", "organ"}
    time.sleep(0.2)
    assert sent(skill, "ovos.midi.events")


def test_changes_while_it_plays(skill):
    skill.handle_jam(MagicMock(data={"utterance": "let's jam"}))
    skill.converse(Message("", {"utterances": ["drums and piano"]}))
    tempo = skill.jam.state.tempo
    assert skill.converse(Message("", {"utterances": ["faster"]})) and skill.jam.state.tempo > tempo
    assert skill.converse(Message("", {"utterances": ["make it reggae"]})) and skill.jam.state.style.name == "reggae"
    assert skill.converse(Message("", {"utterances": ["in G minor"]})) and skill.jam.state.key.name == "Gm"
    assert skill.converse(Message("", {"utterances": ["no more piano"]})) and skill.jam.state.parts == ["drums"]
    assert said(skill)[-1] == "removed"
    assert not skill.converse(Message("", {"utterances": ["what's the weather like"]}))


def test_finish_and_thanks(skill):
    skill.handle_jam(MagicMock(data={"utterance": "jam a swing with drums at 200"}))
    assert skill.jam.state.parts == ["drums"] and skill.jam.state.tempo == 200
    skill.converse(Message("", {"utterances": ["let's finish"]}))
    time.sleep(2 * skill.jam.bar_seconds if skill.jam else 3)
    assert "the_end" in said(skill) and skill.jam is None


def test_no_band(skill):
    skill.bus.band = None
    skill.handle_jam(MagicMock(data={"utterance": "let's jam"}))
    skill.speak_dialog.assert_called_with("no_midi")
    assert skill.jam is None


def test_not_jamming_converse_says_nothing(skill):
    assert skill.converse(Message("", {"utterances": ["drums"]})) is False
    assert skill.can_converse(Message("", {"utterances": ["drums"]})) is False


def test_can_converse_only_for_the_band(skill):
    """OVOS asks the skill first whether a sentence is for it."""
    skill.handle_jam(MagicMock(data={"utterance": "let's jam"}))
    assert skill.can_converse(Message("", {"utterances": ["drums"]}))
    assert skill.can_converse(Message("", {"utterances": ["make it funky"]}))
    assert not skill.can_converse(Message("", {"utterances": ["what time is it"]}))
    assert issubclass(sk.JamBandSkill, sk.ConversationalSkill)


def test_locales_match():
    langs = sorted(p.name for p in (ROOT / "locale").iterdir())
    assert langs == ["ca-ES", "da-DK", "de-DE", "en-US", "es-ES", "eu-ES", "fr-FR", "gl-ES", "it-IT", "nl-NL",
                     "pt-BR", "pt-PT"]
    files = {p.name for p in (ROOT / "locale" / "en-US").iterdir()}
    for lang in langs:
        assert {p.name for p in (ROOT / "locale" / lang).iterdir()} == files, lang


def say(skill, words):
    return skill.converse(Message("", {"utterances": [words]}))


def test_guided(skill):
    skill.handle_guided(MagicMock(data={"utterance": "help me make a jam"}))
    assert said(skill)[-1] == "guide_style" and skill.can_converse(Message("", {"utterances": ["blues"]}))
    assert say(skill, "a blues please") and said(skill)[-1] == "guide_key"
    assert say(skill, "E") and skill.jam.state.key.name == "E" and skill.jam.state.parts == ["drums"]
    assert said(skill)[-1] == "guide_first"
    assert say(skill, "yes") and skill.jam.state.parts == ["drums", "bass"] and said(skill)[-1] == "guide_next"
    assert say(skill, "no thanks") and said(skill)[-1] == "guide_free"
    assert say(skill, "a guitar solo") and said(skill)[-1] == "solo" and skill.jam.solo["part"] == "guitar"


def test_finish_save_and_play_again(skill, monkeypatch, tmp_path):
    monkeypatch.setattr(sk, "SAVE_AFTER_BARS", 0)
    skill.handle_jam(MagicMock(data={"utterance": "jam a funk with drums at 220"}))
    assert say(skill, "a break") and said(skill)[-1] == "break"
    say(skill, "let's finish")
    time.sleep(3 * 60 * 4 / 220)
    assert said(skill)[-2:] == ["the_end", "save_ask"]
    assert say(skill, "yes") and said(skill)[-1] == "save_name"
    assert say(skill, "Friday funk") and said(skill)[-1] == "saved"
    assert (tmp_path / "jams" / "friday-funk.json").exists() and (tmp_path / "jams" / "friday-funk.mid").exists()
    skill.handle_play_saved(MagicMock(data={"name": "friday funk"}))
    assert said(skill)[-1] == "playing" and skill.jam.state.style.name == "funk"
    skill.handle_play_saved(MagicMock(data={"name": "kaffeblues"}))      # one that came with it, by its Danish name
    assert said(skill)[-1] == "playing" and skill.jam.replaying and skill.jam.state.style.name == "blues"
    assert say(skill, "faster") and "take_over" in said(skill)[-2:] and not skill.jam.replaying


def test_a_tune_everybody_knows(skill):
    skill.handle_jam(MagicMock(data={"utterance": "jam a reggae over frere jacques"}))
    assert said(skill)[-1] == "tune" and skill.jam.state.melody and skill.jam.state.style.name == "reggae"
    assert skill.jam.state.key.name == "C" and len(skill.jam.state.chords) == 8
    assert say(skill, "now ode to joy") and skill.jam.state.melody.bars == 8


def test_said_notes_while_jamming(skill):
    skill.handle_jam(MagicMock(data={"utterance": "let's jam with drums"}))
    assert say(skill, "the notes are A C E A G E") and said(skill)[-1] == "got_melody"
    assert skill.jam.state.melody.pitches()[0] % 12 == 9 and skill.jam.state.lead == "sax"
    assert say(skill, "the melody on guitar") and skill.jam.state.lead == "guitar"


def test_surprise_and_the_lists(skill):
    skill.handle_surprise(MagicMock(data={"utterance": "surprise me"}))
    assert said(skill)[-1] == "surprise" and skill.jam.replaying and skill.jam.state.melody
    skill.stop()
    skill.handle_list(MagicMock(data={}))
    name, data = skill.speak_dialog.call_args[0]
    assert name == "list" and data["count"] >= 5 and "Coffee blues" in data["names"]
    skill.handle_tunes(MagicMock(data={}))
    assert said(skill)[-1] == "tunes"
    skill.handle_delete(MagicMock(data={"name": "coffee blues"}))
    assert said(skill)[-1] == "cant_delete"


def test_in_danish(skill, monkeypatch):
    monkeypatch.setattr(sk.JamBandSkill, "lang", "da-DK", raising=False)
    skill.handle_jam(MagicMock(data={"utterance": "lad os jamme en reggae over mester jakob"}))
    assert said(skill)[-1] == "tune" and skill.jam.state.style.name == "reggae" and skill.jam.state.melody
    assert say(skill, "en guitar solo") and skill.jam.solo["part"] == "guitar"
    assert say(skill, "et break") and said(skill)[-1] == "break"
    assert say(skill, "forfra") and said(skill)[-1] == "top"
    assert say(skill, "tonerne er a c e a") and said(skill)[-1] == "got_melody"
    assert say(skill, "melodien på trompeter") and skill.jam.state.lead == "brass"
    assert say(skill, "gem det som fredagsreggae") and said(skill)[-1] == "saved"
