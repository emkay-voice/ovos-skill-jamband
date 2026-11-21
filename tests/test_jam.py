import time

from ovos_skill_jamband.jam import Jam
from ovos_skill_jamband.music import Key
from ovos_skill_jamband.styles import CHANNEL, STYLES, BarContext, bar_notes


class Bus:
    def __init__(self):
        self.sent = []

    def __call__(self, t, d):
        self.sent.append((t, d))

    def of(self, t):
        return [d for k, d in self.sent if k == t]


def test_every_style_and_part_plays_in_time():
    for name, style in STYLES.items():
        key = style.key
        prog = [key.chord(d) for d in style.progression]
        for part in CHANNEL:
            ctx = BarContext(prog[0], prog[1], key, 0, False, {part}, {})
            notes = bar_notes(style, part, ctx)
            assert notes, (name, part)
            for kind, beat, ch, pitch, vel, beats in notes:
                assert kind == "note" and 0 <= beat < 4 and ch == CHANNEL[part] and 0 <= pitch < 128 and 0 < vel <= 127


def test_a_bar_ahead_and_changes_on_the_next_bar():
    bus = Bus()
    jam = Jam(bus, "jam", latency=0.05)
    jam.change(style=STYLES["rock"], tempo=200)              # 1.2 s bars
    jam.start()
    jam.add("drums")
    time.sleep(0.3)
    first = bus.of("ovos.midi.events")
    assert first and all(e[2] == 9 for d in first for e in d["events"] if e[0] == "note")
    starts = sorted({d["at"] for d in first})
    assert len(starts) == 2 and abs(starts[1] - starts[0] - jam.bar_seconds) < 1e-6    # this bar and the next
    jam.add("bass")                                          # cancel what was sent, send it again
    time.sleep(0.2)
    assert bus.of("ovos.midi.cancel")
    last = bus.of("ovos.midi.events")[-1]
    assert any(e[2] == CHANNEL["bass"] for e in last["events"] if e[0] == "note")
    jam.stop()
    assert bus.of("ovos.midi.stop") == [{"source": "jam"}]


def test_key_and_style_and_tempo():
    jam = Jam(Bus(), "jam")
    jam.change(style=STYLES["blues"])
    assert jam.state.key == STYLES["blues"].key and jam.state.tempo == STYLES["blues"].tempo
    jam.change(key=Key(7))
    jam.change(style=STYLES["reggae"])                       # a key you asked for stays
    assert jam.state.key == Key(7) and jam.state.tempo == STYLES["reggae"].tempo
    jam.change(tempo=999)
    assert jam.state.tempo == 220


def test_the_end_is_one_big_chord():
    bus = Bus()
    jam = Jam(bus, "jam", latency=0.05)
    jam.change(style=STYLES["swing"], tempo=200, parts=["drums", "bass", "piano"])
    jam.start()
    time.sleep(0.1)
    jam.finish()
    time.sleep(0.3)
    last = bus.of("ovos.midi.events")[-1]["events"]
    assert {e[1] for e in last} == {0} and any(e[3] == 49 for e in last)     # all at once, with a crash
    assert not jam.running
