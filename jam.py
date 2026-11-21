"""The jam: what the band plays now, sent to the MIDI plugin a bar ahead.

ovos-phal-plugin-midi plays every note at the time it is sent for, so the
jam sends the next bar while this one plays. When something changes - "add
the bass", "faster", "make it reggae" - the next bar is taken back
(ovos.midi.cancel) and sent again, changed: the change is heard on the next
bar line, and the music never stops or stumbles.

Besides the groove there are moments: an intro (the end of the chords,
leading into the top), a solo (an instrument improvises for a round), a
break (everyone hits the one and stops for a bar), back to the top, and the
ending. Your melody, when you gave one, is played on top by the lead
instrument, with chords that suit it.

Everything that happens is written down by the bar it happens on (log), so
a jam can be saved and played again exactly - or taken over halfway and
changed: the script plays until you say something.
"""
from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field

from .melody import Melody, lead_line
from .music import Chord, Key, note_in, voicing
from .solo import drum_solo_bar, solo_bar
from .styles import CHANNEL, DEFAULT, PARTS, STYLES, BarContext, Style, _swing, bar_notes, programs

MIN_TEMPO, MAX_TEMPO = 50, 220
#: the melody's channel, and its sound per instrument (General MIDI)
LEAD_CHANNEL = 10
LEAD_PROGRAM = {"piano": 0, "sax": 66, "brass": 56, "guitar": 26, "organ": 17, "strings": 40,
                "bandoneon": 23, "bass": 33, "drums": 0}
SOLO_BARS = 8                     # a solo lasts a round of the chords, at most this


@dataclass
class State:
    style: Style = field(default_factory=lambda: STYLES[DEFAULT])
    key: Key = field(default_factory=lambda: STYLES[DEFAULT].key)
    tempo: int = STYLES[DEFAULT].tempo
    parts: list = field(default_factory=list)     # playing, in the order they came in
    chords: list | None = None                    # your own chords (or your melody's), else the style's
    key_chosen: bool = False                      # asked for: kept when the style changes
    tempo_chosen: bool = False
    melody: Melody | None = None                  # yours, played by `lead` on top
    lead: str = "piano"
    seed: int = 0                                 # the solos are drawn from it

    def progression(self) -> list[Chord]:
        return self.chords or [self.key.chord(d) for d in self.style.progression]

    # ---------------------------------------------------------- saving
    def to_dict(self) -> dict:
        return {"style": self.style.name, "key": [self.key.tonic, self.key.minor], "tempo": self.tempo,
                "parts": list(self.parts), "chords": encode_chords(self.chords),
                "key_chosen": self.key_chosen, "tempo_chosen": self.tempo_chosen,
                "melody": self.melody.to_dict() if self.melody else None, "lead": self.lead, "seed": self.seed}

    @classmethod
    def from_dict(cls, d: dict) -> "State":
        st = cls()
        st.style = STYLES.get(d.get("style"), STYLES[DEFAULT])
        st.key = Key(*d["key"]) if d.get("key") else st.style.key
        st.tempo = int(d.get("tempo", st.style.tempo))
        st.parts = [p for p in d.get("parts", []) if p in PARTS]
        st.chords = decode_chords(d.get("chords"))
        st.key_chosen = bool(d.get("key_chosen"))
        st.tempo_chosen = bool(d.get("tempo_chosen"))
        st.melody = Melody.from_dict(d["melody"]) if d.get("melody") else None
        st.lead = d.get("lead") or "piano"
        st.seed = int(d.get("seed", 0))
        return st


def encode_chords(chords):
    return [[c.root, c.quality] for c in chords] if chords else None


def decode_chords(data):
    return [Chord(int(r), q) for r, q in data] if data else None


def encode_change(kw: dict) -> dict:
    """A change() as JSON."""
    out = {}
    for k, v in kw.items():
        if k == "style":
            out[k] = v.name
        elif k == "key":
            out[k] = [v.tonic, v.minor]
        elif k == "chords":
            out[k] = encode_chords(v)
        elif k == "melody":
            out[k] = v.to_dict() if v else None
        else:
            out[k] = v
    return out


def decode_change(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if k == "style":
            out[k] = STYLES[v]
        elif k == "key":
            out[k] = Key(*v)
        elif k == "chords":
            out[k] = decode_chords(v)
        elif k == "melody":
            out[k] = Melody.from_dict(v) if v else None
        else:
            out[k] = v
    return out


class Jam:
    """`send(msg_type, data)` puts a message on the bus; `latency` is the
    MIDI plugin's (from ovos.midi.status). `script` is a saved jam's log,
    played back (until take_over())."""

    def __init__(self, send, source: str, latency: float = 0.3, on_bar=None,
                 state: State | None = None, script: list | None = None, on_end=None):
        self.send = send
        self.source = source
        self.latency = latency
        self.on_bar = on_bar               # called with (bar, chord, next chord) as each bar starts
        self.on_end = on_end               # called once the last chord has rung
        self._silent = False               # hearing your melody: the band holds still
        self.state = state or State()
        if not self.state.seed:
            self.state.seed = random.randrange(1, 1 << 30)
        self.first = self.state.to_dict()  # how it began: with the log, the whole jam
        self.log: list = []
        self.script = sorted(script or [], key=lambda e: e["bar"])
        self.lock = threading.RLock()
        self.bar = 0                       # the next bar to send
        self.bar_start = None              # wall time of bar `self.bar`
        self.top = 0                       # the bar where the chords begin again
        self.quiet_until = 0               # no melody before this bar (the intro)
        self.solo: dict | None = None      # {"part", "start", "bars"}
        self.break_bar = None
        self.entering: set = set()
        self.memory: dict = {}
        self.ending = False
        self._stop = threading.Event()
        self._thread = None
        self._wake = threading.Event()

    # ------------------------------------------------------------ timing
    @property
    def bar_seconds(self) -> float:
        return 4 * 60.0 / self.state.tempo

    @property
    def replaying(self) -> bool:
        return bool(self.script)

    def position(self, bar: int) -> int:
        """Where in the chords bar `bar` is."""
        return (bar - self.top) % len(self.state.progression())

    def bar_events(self, bar: int) -> list:
        """What the band plays in bar `bar`, in seconds from its start."""
        st = self.state
        prog = st.progression()
        pos = self.position(bar)
        chord, nxt = prog[pos], prog[(pos + 1) % len(prog)]
        solo = self.solo if self.solo and self.solo["start"] <= bar < self.solo["start"] + self.solo["bars"] else None
        ctx = BarContext(chord, nxt, st.key, bar, pos == len(prog) - 1, set(self.entering), self.memory)
        beat = 60.0 / st.tempo
        notes = []
        if bar == 0 or self.entering:
            notes += programs(st.style)
            notes.append(["program", 0, LEAD_CHANNEL, LEAD_PROGRAM.get(st.lead, 0)])
        if self.ending:
            return notes + self._ending_events(chord if pos == 0 else st.key.chord("i" if st.key.minor else "I"), beat)
        if bar == self.break_bar:
            return notes + self._break_events(chord, beat, bar)
        for part in st.parts:
            if solo and part == solo["part"]:
                continue
            notes += bar_notes(st.style, part, ctx)
        extra = []
        if solo:
            k = bar - solo["start"]
            if solo["part"] == "drums":
                extra += drum_solo_bar(ctx, st.seed, k, solo["bars"])
            else:
                ch = LEAD_CHANNEL if solo["part"] == "lead" else CHANNEL[solo["part"]]
                extra += solo_bar(st.style, solo["part"], ctx, ch, st.seed + solo["start"], k, solo["bars"])
        elif st.melody and bar >= self.quiet_until:
            extra += lead_line(st.melody, pos % st.melody.bars, LEAD_CHANNEL)
        if st.style.swing:
            for e in extra:
                e[1] = _swing(e[1])
        notes += extra
        return [self._seconds(n, beat) for n in notes]

    @staticmethod
    def _seconds(n, beat):
        if n[0] == "note":
            return ["note", round(n[1] * beat, 4), n[2], n[3], n[4], round(n[5] * beat, 4)]
        return [n[0], round(n[1] * beat, 4)] + list(n[2:])

    def _schedule(self, bar: int, at: float):
        """Send bar `bar`, starting at wall time `at`."""
        events = [] if self._silent else self.bar_events(bar)
        self.send("ovos.midi.events", {"source": self.source, "at": at, "events": events})

    def _ending_events(self, chord: Chord, beat: float) -> list:
        """The last bar: one big chord, a crash, and the bass on the root."""
        ev = []
        st = self.state
        for part in st.parts:
            ch = CHANNEL[part]
            if part == "drums":
                ev += [["note", 0, 9, 49, 120, 2.5], ["note", 0, 9, 36, 120, 0.3]]
            elif part == "bass":
                ev.append(["note", 0, ch, note_in(chord.root, 33), 112, 3 * beat])
            else:
                for p in voicing(chord, 57 if part != "strings" else 62):
                    ev.append(["note", 0, ch, p, 108, 3 * beat])
        if st.melody:
            ev.append(["note", 0, LEAD_CHANNEL, note_in(chord.root, 67), 104, 3 * beat])
        return ev

    def _break_events(self, chord: Chord, beat: float, bar: int) -> list:
        """A break: everyone on the one, then silence - and the drums lead back in."""
        ev = []
        st = self.state
        for part in st.parts:
            ch = CHANNEL[part]
            if part == "drums":
                ev += [["note", 0, 9, 49, 116, 1.5 * beat], ["note", 0, 9, 36, 116, 0.2 * beat]]
                ev += [["note", (3 + k / 4) * beat, 9, 38 if k % 2 == 0 else 45, 80 + 10 * k, 0.15 * beat]
                       for k in range(4)]
            elif part == "bass":
                ev.append(["note", 0, ch, note_in(chord.root, 33), 112, 0.6 * beat])
            else:
                for p in voicing(chord, 57 if part != "strings" else 62):
                    ev.append(["note", 0, ch, p, 104, 0.6 * beat])
        if st.melody and bar >= self.quiet_until:
            pos = self.position(bar)
            ev += [self._seconds(n, beat) for n in lead_line(st.melody, pos % st.melody.bars, LEAD_CHANNEL)]
        return ev

    def _run(self):
        while not self._stop.is_set():
            with self.lock:
                now = time.time()
                if self.bar_start is None:
                    self.bar_start = now + self.latency + 0.3
                # keep one bar ahead: send bar n when bar n-1 starts
                while self.bar_start - now < self.bar_seconds + self.latency:
                    self._play_script(self.bar)
                    if self._stop.is_set():
                        break
                    self._schedule(self.bar, self.bar_start)
                    started = self.bar
                    if self.on_bar:
                        prog = self.state.progression()
                        pos = self.position(started)
                        threading.Timer(max(0.0, self.bar_start - now), self.on_bar,
                                        (started, prog[pos], prog[(pos + 1) % len(prog)])).start()
                    self.entering = set()
                    if self.ending:
                        self._stop.set()
                        if self.on_end:
                            threading.Timer(max(0.0, self.bar_start - now) + self.bar_seconds, self.on_end).start()
                        break
                    self.bar += 1
                    self.bar_start += self.bar_seconds
                wait = self.bar_start - self.bar_seconds - self.latency - time.time()
            self._wake.clear()
            self._wake.wait(max(0.02, min(wait, 0.5)))

    def _play_script(self, bar: int):
        """A saved jam: do what was done at this bar."""
        while self.script and self.script[0]["bar"] <= bar:
            entry = self.script.pop(0)
            self._apply(entry["do"], entry.get("args") or {})
            self.log.append({"bar": bar, "do": entry["do"], "args": entry.get("args") or {}})

    def _resend(self):
        """A change: take back the bar already sent and send it again (it
        starts at the next bar line)."""
        if self.bar_start is None:
            return
        last_sent = self.bar - 1
        start = self.bar_start - self.bar_seconds
        if start > time.time() + self.latency:          # not playing yet: send it again
            self.send("ovos.midi.cancel", {"source": self.source, "after": start - 0.001})
            self.bar = last_sent
            self.bar_start = start
        self._wake.set()

    # ------------------------------------------------------------ what can happen
    def _apply(self, what: str, args: dict):
        st = self.state
        nxt = self.bar
        if what == "change":
            kw = decode_change(args)
            old_parts = set(st.parts)
            for k, v in kw.items():
                setattr(st, k, v)
            st.key_chosen |= "key" in kw
            st.tempo_chosen |= "tempo" in kw
            if "style" in kw and not st.key_chosen:
                st.key = kw["style"].key
            if "style" in kw and not st.tempo_chosen:
                st.tempo = kw["style"].tempo
            st.tempo = max(MIN_TEMPO, min(MAX_TEMPO, int(st.tempo)))
            self.entering |= set(st.parts) - old_parts
            if {"style", "lead", "melody"} & set(kw):
                self.entering |= set(st.parts) | {"lead"}       # new sounds for everyone
        elif what == "solo":
            part = args.get("part") or "sax"
            plen = len(st.progression())
            bars = args.get("bars") or (plen if plen <= SOLO_BARS else 4)
            self.solo = {"part": part, "start": nxt, "bars": bars}
            self.entering |= {part}
        elif what == "break":
            self.break_bar = nxt
        elif what == "top":
            self.top = nxt
        elif what == "intro":
            plen = len(st.progression())
            k = min(4, plen)
            self.top = nxt - (plen - k)
            self.quiet_until = nxt + k
        elif what == "finish":
            self.ending = True
        elif what == "end":                 # a saved jam that was stopped: end it nicely
            self.ending = True

    def _do(self, what: str, args: dict | None = None):
        with self.lock:
            self._resend()
            self._apply(what, args or {})
            self.log.append({"bar": self.bar, "do": what, "args": args or {}})

    # ------------------------------------------------------------ control
    def start(self):
        self._thread = threading.Thread(target=self._run, name="jam", daemon=True)
        self._thread.start()

    def silent(self, on: bool):
        """Hold still (on) - the time goes on, nothing is played - or play again."""
        with self.lock:
            if on == self._silent:
                return
            self._silent = on
            if on:
                self.send("ovos.midi.stop", {"source": self.source})
                self.entering |= set(self.state.parts) | {"lead"}
            self._resend()

    def take_over(self) -> bool:
        """Stop playing a saved jam's script: from now on it is a live jam. True if it was replaying."""
        with self.lock:
            was = bool(self.script)
            self.script = []
            return was

    def change(self, **kw):
        """Change what is played (parts, style, key, tempo, chords, melody, lead), from the next bar."""
        self._do("change", encode_change(kw))

    def add(self, *parts):
        with self.lock:
            new = [p for p in parts if p not in self.state.parts]
            if new:
                self.change(parts=self.state.parts + new)
            return new

    def remove(self, *parts):
        with self.lock:
            gone = [p for p in parts if p in self.state.parts]
            if gone:
                self.change(parts=[p for p in self.state.parts if p not in gone])
            return gone

    def solo_for(self, part: str, bars: int | None = None):
        """`part` improvises from the next bar, for a round of the chords."""
        self._do("solo", {"part": part, "bars": bars})

    def brk(self):
        """A break on the next bar."""
        self._do("break")

    def from_the_top(self):
        self._do("top")

    def intro(self):
        """The last bars of the chords lead in, then the top (and the melody)."""
        self._do("intro")

    def finish(self):
        """End with a big chord on the next bar line."""
        self._do("finish")

    def stop(self):
        with self.lock:
            if not self.ending:
                self.log.append({"bar": self.bar, "do": "end", "args": {}})
        self._stop.set()
        self._wake.set()
        self.send("ovos.midi.stop", {"source": self.source})

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()

    @property
    def soloing(self) -> str | None:
        s = self.solo
        if s and s["start"] <= self.bar < s["start"] + s["bars"] + 1:
            return s["part"]
        return None

    # ------------------------------------------------------------ saved
    def recording(self) -> dict:
        """The whole jam: how it began and what happened when."""
        with self.lock:
            return {"first": dict(self.first), "log": [dict(e) for e in self.log], "bars": self.bar}


def render(recording: dict, max_bars: int = 400) -> list:
    """A saved jam played without time: [(bar, tempo, events)], events in
    seconds from the bar's start (for a MIDI file)."""
    out = []
    jam = Jam(lambda *_: None, "render", state=State.from_dict(recording["first"]), script=recording.get("log"))
    for bar in range(max_bars):
        jam.bar = bar
        jam._play_script(bar)
        out.append((bar, jam.state.tempo, jam.bar_events(bar)))
        jam.entering = set()
        if jam.ending:
            break
        if not jam.script and bar >= recording.get("bars", 0):
            break
    return out
