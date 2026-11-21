"""ovos-skill-jamband: a band you lead with your voice.

  "let's jam"                 "What do we start with? Drums?"
  "drums"                     the drums start - "Yeah! That's good."
  "and a bass"                the bass comes in on the next bar
  "the whole band"            "And now... the whole orchestra!"
  "faster" / "slower"         "make it reggae"   "in G minor"
  "no more piano"             "let's finish"     (a big last chord)

Styles: swing, blues, rock, pop, funk, disco, reggae, bossa, tango - each
with its own groove for every part, in any key. The band is
ovos-phal-plugin-midi, the device's MIDI instrument: the jam sends it a
bar ahead, so a change is heard on the next bar line and the music never
stops. While the jam plays, what you say goes to it first (no wake word
needed after Emkay answers: it listens again).

The pieces: music.py (keys, chords), styles.py (what each part plays),
jam.py (a bar ahead to the plugin), words.py (what a sentence asks for),
screen.py (the chord and the band on the screen).
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from ovos_bus_client.message import Message
from ovos_workshop.decorators import intent_handler
from ovos_workshop.skills import OVOSSkill

try:   # ovos-workshop 8: converse is ConversationalSkill's
    from ovos_workshop.skills.converse import ConversationalSkill
except ImportError:  # before it, every OVOSSkill could converse
    ConversationalSkill = OVOSSkill

from . import screen
from .jam import Jam
from .styles import DEFAULT, PARTS, STYLES
from .words import Words

SKILL_ROOT = Path(__file__).resolve().parent
MIDI_WAIT = 3.0             # seconds to wait for the MIDI plugin to answer
KEEP_ACTIVE_BARS = 8        # say so to OVOS every this many bars: what you say goes to the jam first


class JamBandSkill(ConversationalSkill):

    def __init__(self, *args, **kwargs):
        # before OVOSSkill's own setup: its intents can be asked before initialize() has run
        self.jam: Jam | None = None
        self._words: dict = {}
        self._lock = threading.RLock()
        super().__init__(*args, **kwargs)

    def words(self) -> Words:
        lang = self.lang
        if lang not in self._words:
            self._words[lang] = Words(SKILL_ROOT / "locale", lang)
        return self._words[lang]

    # ------------------------------------------------------------ starting
    def _band(self):
        """ovos-phal-plugin-midi's status, or None when it doesn't answer."""
        r = self.bus.wait_for_response(Message("ovos.midi.status"), "ovos.midi.status.response",
                                       timeout=MIDI_WAIT)
        if r is None or r.data.get("engine") in (None, "none"):
            return None
        return r.data

    @intent_handler("jam.intent")
    def handle_jam(self, message):
        utterance = message.data.get("query") or message.data.get("utterance", "")
        band = self._band()
        if not band:
            self.speak_dialog("no_midi")
            return
        self.stop()
        w = self.words()
        style = STYLES[w.style(utterance) or DEFAULT]
        with self._lock:
            self.jam = Jam(self._send, self.skill_id, float(band.get("latency", 0.3)), on_bar=self._on_bar)
            change = {"style": style}
            key = w.key(utterance)
            if key:
                change["key"] = key
            tempo = w.tempo(utterance)
            if tempo:
                change["tempo"] = tempo
            self.jam.change(**change)
            self.jam.start()
        self._keep_active()
        parts = w.parts(utterance)
        if parts:
            self._add(parts)
        else:
            self.speak_dialog("start", {"style": style.name, "key": w.spoken_key(self.jam.state.key)},
                              expect_response=True)

    # ------------------------------------------------------------ while it plays
    def can_converse(self, message=None) -> bool:
        """OVOS asks first: is this sentence for the band?"""
        if not self.jam or not self.jam.running:
            return False
        utterances = (message.data.get("utterances") if message else None) or []
        return not utterances or any(self.understand(u) for u in utterances)

    def converse(self, message=None):
        if not self.jam or not self.jam.running or message is None:
            return False
        for utterance in message.data.get("utterances") or []:
            action = self.understand(utterance)
            if action:
                self.do(*action)
                return True
        return False

    def understand(self, utterance: str):
        """What `utterance` asks of the band: (what, value), or None."""
        w, st = self.words(), self.jam.state
        if w.has(utterance, "finish"):
            return ("finish", None)
        parts = w.parts(utterance)
        if w.has(utterance, "remove") and parts:
            return ("remove", parts)
        if w.has(utterance, "everyone"):
            return ("everyone", st.style.band)
        if parts:
            return ("add", parts)
        style = w.style(utterance)
        if style and STYLES[style] is not st.style:
            return ("style", style)
        key = w.key(utterance)
        if key:
            return ("key", key)
        tempo = w.tempo(utterance)
        if tempo:
            return ("tempo", tempo)
        if w.has(utterance, "faster"):
            return ("faster", None)
        if w.has(utterance, "slower"):
            return ("slower", None)
        return None

    def do(self, what, value):
        w, jam = self.words(), self.jam
        if what == "finish":
            self._finish()
        elif what == "remove":
            gone = jam.remove(*value)
            if gone:
                self.speak_dialog("removed", {"part": self._name(gone[0])}, expect_response=True)
        elif what in ("everyone", "add"):
            self._add(value, everyone=what == "everyone")
        elif what == "style":
            jam.change(style=STYLES[value])
            self.speak_dialog("style", {"style": value}, expect_response=True)
        elif what == "key":
            jam.change(key=value)
            self.speak_dialog("key", {"key": w.spoken_key(value)}, expect_response=True)
        elif what == "tempo":
            jam.change(tempo=value)
            self.speak_dialog("tempo", {"tempo": jam.state.tempo}, expect_response=True)
        else:
            up = what == "faster"
            jam.change(tempo=round(jam.state.tempo * (1.12 if up else 0.89)))
            self.speak_dialog(what, expect_response=True)

    def command(self, utterance: str) -> bool:
        """Do what `utterance` asks of the band; False when it asks nothing of it."""
        action = self.understand(utterance)
        if action:
            self.do(*action)
        return bool(action)

    def _add(self, parts, everyone=False):
        new = self.jam.add(*parts)
        if not new:
            self.speak_dialog("what_else", expect_response=True)
            return
        comment = "in_band" if everyone or len(new) >= 3 else f"in_{new[-1]}"
        self.speak_dialog(comment, expect_response=True)

    def _name(self, part: str) -> str:
        return self.dialog_renderer.render(f"name_{part}", {}) if self.dialog_renderer else part

    def _finish(self):
        """A big last chord on the next bar line, then thanks."""
        jam = self.jam
        jam.finish()
        delay = max(0.0, (jam.bar_start or 0) - time.time()) + jam.bar_seconds

        def thanks():
            if self.jam is jam:
                self.jam = None
                self.gui.release()
                self.speak_dialog("the_end")
        threading.Timer(delay, thanks).start()

    def _keep_active(self):
        """What is said goes to the jam first (converse) while it plays."""
        activate = getattr(self, "activate", None) or getattr(self, "make_active", None)
        if activate:
            try:
                activate()
            except Exception:
                pass

    # ------------------------------------------------------------ bus and screen
    def _send(self, msg_type: str, data: dict):
        self.bus.emit(Message(msg_type, data, {"skill_id": self.skill_id}))

    def _on_bar(self, bar, chord, next_chord):
        jam = self.jam
        if not jam or not jam.running:
            return
        if bar % KEEP_ACTIVE_BARS == 0:
            self._keep_active()
        st = jam.state
        prog = st.progression()
        upcoming = [prog[(bar + k) % len(prog)] for k in range(1, 5)]
        names = {p: self._name(p) for p in PARTS}
        title = f"{st.style.name.title()} · {st.key.name} · {st.tempo} bpm"
        self.gui["image"] = screen.render(title, chord, upcoming, st.parts, names)
        if bar == 0:
            self.gui["title"] = ""
            self.gui["caption"] = ""
            self.gui["fill"] = "PreserveAspectFit"
            self.gui["background_color"] = screen.BG
            self.gui.show_page("SYSTEM_ImageFrame", override_idle=True)

    def stop(self):
        with self._lock:
            jam, self.jam = self.jam, None
        if jam is None:
            return False
        jam.stop()
        self.gui.release()
        return True
