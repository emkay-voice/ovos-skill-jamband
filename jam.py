"""The jam: what the band plays now, sent to the MIDI plugin a bar ahead.

ovos-phal-plugin-midi plays every note at the time it is sent for, so the
jam sends the next bar while this one plays. When something changes - "add
the bass", "faster", "make it reggae" - the next bar is taken back
(ovos.midi.cancel) and sent again, changed: the change is heard on the next
bar line, and the music never stops or stumbles.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from .music import Chord, Key
from .styles import CHANNEL, DEFAULT, STYLES, BarContext, Style, bar_notes, programs

MIN_TEMPO, MAX_TEMPO = 50, 220


@dataclass
class State:
    style: Style = field(default_factory=lambda: STYLES[DEFAULT])
    key: Key = field(default_factory=lambda: STYLES[DEFAULT].key)
    tempo: int = STYLES[DEFAULT].tempo
    parts: list = field(default_factory=list)     # playing, in the order they came in
    chords: list | None = None                    # your own chords, else the style's progression
    key_chosen: bool = False                      # asked for: kept when the style changes
    tempo_chosen: bool = False

    def progression(self) -> list[Chord]:
        return self.chords or [self.key.chord(d) for d in self.style.progression]


class Jam:
    """`send(msg_type, data)` puts a message on the bus; `latency` is the
    MIDI plugin's (from ovos.midi.status)."""

    def __init__(self, send, source: str, latency: float = 0.3, on_bar=None):
        self.send = send
        self.source = source
        self.latency = latency
        self.on_bar = on_bar               # called with (bar, chord, next chord) as each bar starts
        self.state = State()
        self.lock = threading.RLock()
        self.bar = 0                       # the next bar to send
        self.bar_start = None              # wall time of bar `self.bar`
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

    def _schedule(self, bar: int, at: float):
        """Send bar `bar`, starting at wall time `at`."""
        st = self.state
        prog = st.progression()
        chord = prog[bar % len(prog)]
        nxt = prog[(bar + 1) % len(prog)]
        ctx = BarContext(chord, nxt, st.key, bar, bar % len(prog) == len(prog) - 1,
                         set(self.entering), self.memory)
        beat = 60.0 / st.tempo
        events = []
        if bar == 0 or self.entering:
            events += programs(st.style)
        for part in st.parts:
            for kind, b, ch, pitch, vel, beats in bar_notes(st.style, part, ctx):
                events.append([kind, round(b * beat, 4), ch, pitch, vel, round(beats * beat, 4)])
        if self.ending:
            events = self._ending_events(chord if bar % len(prog) == 0 else st.key.chord("i" if st.key.minor else "I"), beat)
        self.send("ovos.midi.events", {"source": self.source, "at": at, "events": events})

    def _ending_events(self, chord: Chord, beat: float) -> list:
        """The last bar: one big chord, a crash, and the bass on the root."""
        from .music import note_in, voicing
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
        return ev

    def _run(self):
        while not self._stop.is_set():
            with self.lock:
                now = time.time()
                if self.bar_start is None:
                    self.bar_start = now + self.latency + 0.3
                # keep one bar ahead: send bar n when bar n-1 starts
                while self.bar_start - now < self.bar_seconds + self.latency:
                    self._schedule(self.bar, self.bar_start)
                    started = self.bar
                    if self.on_bar:
                        prog = self.state.progression()
                        threading.Timer(max(0.0, self.bar_start - now), self.on_bar,
                                        (started, prog[started % len(prog)],
                                         prog[(started + 1) % len(prog)])).start()
                    self.entering = set()
                    if self.ending:
                        self._stop.set()
                        break
                    self.bar += 1
                    self.bar_start += self.bar_seconds
                wait = self.bar_start - self.bar_seconds - self.latency - time.time()
            self._wake.clear()
            self._wake.wait(max(0.02, min(wait, 0.5)))

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

    # ------------------------------------------------------------ control
    def start(self):
        self._thread = threading.Thread(target=self._run, name="jam", daemon=True)
        self._thread.start()

    def change(self, **kw):
        """Change what is played (parts, style, key, tempo, chords), from the next bar."""
        with self.lock:
            st = self.state
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
            if "style" in kw:
                self.entering |= set(st.parts)      # new programs for everyone
            self._resend()

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

    def finish(self):
        """End with a big chord on the next bar line."""
        with self.lock:
            self.ending = True
            self._resend()

    def stop(self):
        self._stop.set()
        self._wake.set()
        self.send("ovos.midi.stop", {"source": self.source})

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()
