import time
from unittest.mock import MagicMock

import pytest
from ovos_bus_client.message import Message

import ovos_skill_jamband as sk

from conftest import ROOT


@pytest.fixture
def skill(monkeypatch):
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
