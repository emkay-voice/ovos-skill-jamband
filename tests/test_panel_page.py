"""The page this skill has in ovos-control-panel, described in
controlpanel.json: the file, its strings in every language, and the skill's
answers over the bus."""
import json
import re
from unittest.mock import MagicMock

import pytest
from ovos_bus_client.message import Message

import ovos_skill_jamband as sk
from ovos_skill_jamband.compose import compose
from ovos_skill_jamband.jams import Jams

ROOT = sk.SKILL_ROOT
PAGE = json.loads((ROOT / "controlpanel.json").read_text(encoding="utf-8"))


def test_the_page_names_files_that_exist_and_its_own_messages():
    assert PAGE["controlpanel"] == 1 and PAGE["id"] == "jamband" and PAGE["group"] == "music"
    assert (ROOT / PAGE["icon"]).is_file()
    sent = re.findall(r'"(?:query|send|download)": "([^"]+)"', (ROOT / "controlpanel.json").read_text())
    assert sent and all(m.startswith(PAGE["bus"]) for m in sent)


def test_the_page_speaks_every_language():
    files = {p.parent.name: json.loads(p.read_text(encoding="utf-8"))
             for p in (ROOT / "locale").glob("*/controlpanel.json")}
    assert {f.split("-")[0] for f in files} == {"ca", "da", "de", "en", "es", "eu", "fr", "gl", "it", "nl", "pt"}
    keys = set(files["en-US"])
    for lang, table in files.items():
        assert set(table) == keys, lang
        assert all(text.strip() for text in table.values()), lang
        assert "{playing}" in table["jamband.playing"] and "{style}" in table["jamband.meta"], lang
    used = set(re.findall(r'"(jamband\.[\w.]+)"', (ROOT / "controlpanel.json").read_text()))
    assert used <= keys and keys - used <= {"nav.group.music"}


def test_the_panel_reads_it(tmp_path):
    described = pytest.importorskip("ovos_webui.described")
    page, refs = described.check(PAGE, "ovos-skill-jamband")
    assert [b["type"] for b in page["blocks"]] == ["text", "status", "list", "text"]
    assert "b2.rename" in refs and refs["b2.a2"]["confirm"]


def test_your_jams_are_renamed_deleted_and_made_into_midi(tmp_path):
    jams = Jams(tmp_path / "mine", ROOT / "jams")
    jams.save("Fredags blues", compose(style_name="blues", tune_id="ode_to_joy"), lang="da-DK")
    mine = jams.get("fredags-blues")
    assert mine and not mine.get("bundled")
    renamed = jams.rename("fredags-blues", "Lørdagsblues")
    assert renamed["id"] == "lordagsblues" and renamed["name"] == "Lørdagsblues"
    assert not (tmp_path / "mine" / "fredags-blues.json").exists()
    assert (tmp_path / "mine" / "lordagsblues.mid").read_bytes().startswith(b"MThd")
    theirs = next(d for d in jams.all() if d.get("bundled"))
    assert theirs["id"].startswith("skill:")
    with pytest.raises(ValueError):
        jams.rename(theirs["id"], "Mine now")
    assert jams.midi(theirs["id"]).startswith(b"MThd"), "the skill's own are made on the fly"
    jams.save("Søndag", compose(style_name="swing", tune_id="ode_to_joy"))
    with pytest.raises(ValueError, match="taken"):
        jams.rename("sondag", "lørdagsblues")
    assert jams.remove(theirs["id"]) is False
    assert jams.remove("lordagsblues") is True and jams.get("lordagsblues") is None


@pytest.fixture
def skill(monkeypatch, tmp_path):
    from ovos_utils.fakebus import FakeBus
    bus = FakeBus()
    monkeypatch.setattr(sk.OVOSSkill, "__init__", lambda self, *a, **k: None)
    monkeypatch.setattr(sk.ConversationalSkill, "__init__", lambda self, *a, **k: None)
    s = sk.JamBandSkill()
    s.skill_id = "ovos-skill-jamband.test"
    monkeypatch.setattr(sk.JamBandSkill, "lang", "da-DK", raising=False)
    monkeypatch.setattr(sk.JamBandSkill, "bus", bus, raising=False)
    monkeypatch.setattr(sk.JamBandSkill, "gui", MagicMock(), raising=False)
    s.speak_dialog = MagicMock()
    s.file_system = MagicMock(path=str(tmp_path))
    monkeypatch.setattr(sk.JamBandSkill, "_play", lambda self, d: True)
    monkeypatch.setattr(sk.JamBandSkill, "add_event", lambda self, t, h: bus.on(t, h), raising=False)
    s.initialize()
    s.jams.save("Fredags blues", compose(style_name="blues", tune_id="ode_to_joy"), lang="da-DK")
    return s, bus


def ask(bus, msg_type, data=None):
    return bus.wait_for_response(Message(msg_type, data or {}), timeout=3).data


def test_the_skill_answers_the_page(skill):
    _, bus = skill
    jams = ask(bus, "ovos.jamband.jams.list")["jams"]
    assert jams[0]["id"] == "fredags-blues" and jams[0]["style"] == "blues" and not jams[0]["bundled"]
    coffee = next(j for j in jams if j["id"] == "skill:coffee-blues")
    assert coffee["bundled"] and coffee["name"] == "Kaffeblues", "the skill's own in the device's language"
    assert coffee["key"] == "E" and coffee["tempo"] == 96
    renamed = ask(bus, "ovos.jamband.jams.rename", {"id": "fredags-blues", "name": "Lørdagsblues"})
    assert renamed["jams"][0]["name"] == "Lørdagsblues"
    assert ask(bus, "ovos.jamband.jams.rename", {"id": "skill:coffee-blues", "name": "x"})["error"]
    midi = ask(bus, "ovos.jamband.jams.midi", {"id": "lordagsblues"})
    import base64
    assert base64.b64decode(midi["midi"]).startswith(b"MThd") and midi["name"] == "Lørdagsblues"
    assert ask(bus, "ovos.jamband.jams.play", {"id": "skill:coffee-blues"}) == {"playing": "Kaffeblues"}
    assert ask(bus, "ovos.jamband.jams.delete", {"id": "skill:coffee-blues"})["error"]
    left = ask(bus, "ovos.jamband.jams.delete", {"id": "lordagsblues"})["jams"]
    assert all(j["bundled"] for j in left)
