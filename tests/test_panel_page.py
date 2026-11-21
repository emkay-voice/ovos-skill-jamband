"""The page this skill adds to ovos-control-panel: its description, its
strings in every language, the skill's answers over the bus, and the routes."""
import base64
import json
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import ovos_skill_jamband as sk
from ovos_skill_jamband import panel
from ovos_skill_jamband.compose import compose
from ovos_skill_jamband.jams import Jams

PANEL = Path(panel.__file__).parent
LANGS = {"ca", "da", "de", "en", "es", "eu", "fr", "gl", "it", "nl", "pt"}


def test_the_page_description_names_files_that_exist():
    page = panel.PAGE
    assert page["api_version"] == 1 and page["id"] == "jamband" and page["group"] == "music"
    assert panel.MUSIC in page["groups"]
    for key in ("html", "icon"):
        assert (PANEL / page[key]).is_file(), key


def test_the_page_speaks_every_language():
    files = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (PANEL / "i18n").glob("*.json")}
    assert set(files) == LANGS
    keys = set(files["en"])
    for lang, table in files.items():
        assert set(table) == keys, lang
        assert all(text.strip() for text in table.values()), lang
        assert "{style}" in table["jamband.meta"] and "{date}" in table["jamband.saved_on"], lang
    html = (PANEL / "page.html").read_text(encoding="utf-8")
    used = set(re.findall(r'data-i18n="([^"]+)"', html)) | set(re.findall(r'"(jamband\.[\w.]+)"', html))
    assert used <= keys and keys - used <= {"jamband.title", "nav.group.music"}


def test_your_jams_are_renamed_deleted_and_made_into_midi(tmp_path):
    jams = Jams(tmp_path / "mine", sk.SKILL_ROOT / "jams")
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


pytest.importorskip("fastapi")
pytest.importorskip("httpx")


@pytest.fixture
def client(monkeypatch, tmp_path):
    from fastapi import APIRouter, FastAPI
    from fastapi.testclient import TestClient
    from ovos_utils.fakebus import FakeBus

    monkeypatch.setitem(sys.modules, "ovos_webui", None)   # the bus client's own wait
    bus = FakeBus()
    monkeypatch.setattr(sk.OVOSSkill, "__init__", lambda self, *a, **k: None)
    monkeypatch.setattr(sk.ConversationalSkill, "__init__", lambda self, *a, **k: None)
    skill = sk.JamBandSkill()
    skill.skill_id = "ovos-skill-jamband.test"
    monkeypatch.setattr(sk.JamBandSkill, "lang", "da-DK", raising=False)
    monkeypatch.setattr(sk.JamBandSkill, "bus", bus, raising=False)
    monkeypatch.setattr(sk.JamBandSkill, "gui", MagicMock(), raising=False)
    skill.speak_dialog = MagicMock()
    skill.file_system = MagicMock(path=str(tmp_path))
    monkeypatch.setattr(sk.JamBandSkill, "_play", lambda self, d: True)
    monkeypatch.setattr(sk.JamBandSkill, "add_event", lambda self, t, h: bus.on(t, h), raising=False)
    skill.initialize()
    skill.jams.save("Fredags blues", compose(style_name="blues", tune_id="ode_to_joy"), lang="da-DK")

    class R:
        api = APIRouter(prefix="/api")
        privileged = APIRouter(prefix="/api")

        @staticmethod
        def need_bus():
            return bus

        @staticmethod
        def bus():
            return bus

    panel.routes(R)
    app = FastAPI()
    app.include_router(R.api)
    app.include_router(R.privileged)
    with TestClient(app) as c:
        yield c, skill


def test_the_page_lists_yours_and_the_skills_own(client):
    c, _ = client
    jams = c.get("/api/jamband/jams").json()["jams"]
    assert jams[0]["id"] == "fredags-blues" and jams[0]["style"] == "blues" and not jams[0]["bundled"]
    coffee = next(j for j in jams if j["id"] == "skill:coffee-blues")
    assert coffee["bundled"] and coffee["name"] == "Kaffeblues", "the skill's own in the device's language"
    assert coffee["key"] == "E" and coffee["tempo"] == 96


def test_rename_delete_play_and_download(client):
    c, _ = client
    r = c.post("/api/jamband/rename", json={"id": "fredags-blues", "name": "Lørdagsblues"})
    assert r.status_code == 200 and r.json()["jams"][0]["name"] == "Lørdagsblues"
    assert c.post("/api/jamband/rename", json={"id": "skill:coffee-blues", "name": "x"}).status_code == 400
    assert c.post("/api/jamband/rename", json={"id": "../etc", "name": "x"}).status_code == 422
    midi = c.get("/api/jamband/midi", params={"id": "lordagsblues"})
    assert midi.status_code == 200 and midi.content.startswith(b"MThd")
    assert "filename*=UTF-8''L%C3%B8rdagsblues.mid" in midi.headers["content-disposition"]
    assert c.post("/api/jamband/play", json={"id": "skill:coffee-blues"}).json() == {"playing": "Kaffeblues"}
    assert c.post("/api/jamband/delete", json={"id": "skill:coffee-blues"}).status_code == 400
    left = c.post("/api/jamband/delete", json={"id": "lordagsblues"}).json()["jams"]
    assert all(j["bundled"] for j in left)
