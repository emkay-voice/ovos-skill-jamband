import time

from ovos_skill_jamband.jam import Jam, render
from ovos_skill_jamband.jams import Jams, midi_bytes
from ovos_skill_jamband.melody import Melody
from ovos_skill_jamband.styles import STYLES
from ovos_skill_jamband.compose import compose


def live_bars(sent):
    """What was played, bar by bar: the last bar sent for each start time (a cancel takes back)."""
    bars = {}
    for t, d in sent:
        if t == "ovos.midi.cancel":
            for k in [k for k in bars if k > d["after"]]:
                del bars[k]
        if t == "ovos.midi.events":
            bars[d["at"]] = d["events"]
    return [bars[k] for k in sorted(bars)]


def test_a_saved_jam_plays_as_it_was_played():
    sent = []
    jam = Jam(lambda t, d: sent.append((t, d)), "jam", latency=0.02)
    jam.change(style=STYLES["blues"], tempo=220, parts=["drums"])
    jam.intro()
    jam.start()
    time.sleep(1.2)
    jam.add("bass", "piano")
    time.sleep(1.2)
    jam.solo_for("sax")
    time.sleep(2.4)
    jam.brk()
    time.sleep(1.2)
    jam.change(melody=Melody.of([(0, 64, 1), (1, 67, 1), (2, 69, 2)]), lead="sax")
    time.sleep(1.2)
    jam.finish()
    time.sleep(1.4)
    played = live_bars(sent)
    again = [ev for _, _, ev in render(jam.recording())]
    assert len(played) == len(again)
    for a, b in zip(played, again):
        assert sorted(map(str, a)) == sorted(map(str, b))
    assert any(e[2] == 10 for bar in played for e in bar if e[0] == "note")        # the melody


def test_replay_then_take_over():
    rec = compose(tune_id="frere_jacques", style_name="pop")
    sent = []
    from ovos_skill_jamband.jam import State
    jam = Jam(lambda t, d: sent.append((t, d)), "jam", latency=0.02, state=State.from_dict(rec["first"]),
              script=rec["log"])
    jam.change(tempo=220)
    jam.start()
    time.sleep(0.6)
    assert jam.replaying and jam.take_over() and not jam.replaying
    jam.finish()
    time.sleep(1.5)
    assert not jam.running


def test_save_find_delete(tmp_path):
    jams = Jams(tmp_path / "mine", tmp_path / "bundled")
    rec = compose(style_name="swing", tune_id="ode_to_joy")
    jams.save("Fredags blues", rec, lang="da-DK")
    assert (tmp_path / "mine" / "fredags-blues.mid").read_bytes().startswith(b"MThd")
    assert jams.find("fredags blues")["name"] == "Fredags blues"
    assert jams.find("fredag")["name"] == "Fredags blues"
    assert jams.names() == ["Fredags blues"]
    assert jams.delete("fredags blues") == "Fredags blues" and jams.names() == []


def test_emkays_own_jam_has_it_all():
    rec = compose(tune_id="twinkle", style_name="bossa")
    did = [e["do"] for e in rec["log"]]
    assert did[:2] == ["change", "intro"] and "solo" in did and "break" in did and did[-1] == "finish"
    bars = render(rec)
    assert len(bars) == rec["bars"]
    assert midi_bytes(rec)[:4] == b"MThd"
