"""ovos-skill-jamband: a band you lead with your voice.

  "let's jam"                 "What do we start with? Drums?"
  "drums"                     the drums start - "Yeah! That's good."
  "and a bass"                the bass comes in on the next bar
  "the whole band"            "And now... the whole orchestra!"
  "faster" / "slower"         "make it reggae"   "in G minor"
  "a sax solo"  "a break"     "from the top"     "an intro"
  "here's my melody"          hum it, play it on a MIDI keyboard - or say
                              it: "the notes are C D E C" - and the band
                              plays it, with chords that suit it
  "a reggae over Frère Jacques"  a tune everybody knows (tunes.py: free
                              ones - folk songs, nursery rhymes, the classics)
  "let's finish"              a big last chord - "Shall I save that jam?"

  "surprise me"               Emkay's own jam: a tune, a style, an intro,
                              solos, a break, the ending - interrupt it to
                              change it, save it after

  "help me make a jam"        Emkay asks: which style, which key, and
                              brings the band in one by one
  "play my jam Friday blues"  a saved jam, played as it was - say anything
                              and it is yours to change
  "what jams do I have?"      yours, and the ones that come with the skill

Styles: swing, blues, rock, pop, funk, disco, reggae, bossa, tango - each
with its own groove for every part, in any key. The band is
ovos-phal-plugin-midi, the device's MIDI instrument: the jam sends it a
bar ahead, so a change is heard on the next bar line and the music never
stops. While the jam plays, what you say goes to it first (no wake word
needed after Emkay answers: it listens again).

The pieces: music.py (keys, chords), styles.py (what each part plays),
solo.py (improvising), melody.py (your melody: said, played or hummed, and
its chords), tunes.py (the library), compose.py (Emkay's own jams), listen.py (the microphone and the keyboard), jam.py (a bar
ahead to the plugin, and the log that saves it), jams.py (saved jams and
MIDI files), words.py (what a sentence asks for), screen.py (the screen).
"""
from __future__ import annotations

import random
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

from . import melody as M
from . import screen
from . import tunes as T
from .compose import LEADS, chords_for, compose
from .jam import Jam, State
from .jams import Jams
from .listen import Listen
from .styles import DEFAULT, PARTS, STYLES
from .words import Words

SKILL_ROOT = Path(__file__).resolve().parent
MIDI_WAIT = 3.0             # seconds to wait for the MIDI plugin to answer
KEEP_ACTIVE_BARS = 8        # say so to OVOS every this many bars: what you say goes to the jam first
ANSWER_WAIT = 25.0          # a question Emkay asked waits this long for its answer
SAVE_AFTER_BARS = 8         # a jam this long is worth offering to save
#: who solos when you just say "a solo"
SOLOIST = {"swing": "sax", "blues": "guitar", "rock": "guitar", "pop": "piano", "funk": "sax",
           "disco": "brass", "reggae": "organ", "bossa": "sax", "tango": "bandoneon"}


class JamBandSkill(ConversationalSkill):

    def __init__(self, *args, **kwargs):
        # before OVOSSkill's own setup: its intents can be asked before initialize() has run
        self.jam: Jam | None = None
        self._words: dict = {}
        self._lock = threading.RLock()
        self.asking: dict | None = None        # a question Emkay asked: {"what", "until", ...}
        self.playing_name = ""                  # the saved (or Emkay's own) jam being played: the screen's title
        self.offer_save = True                  # at the end: "Shall I save it?" (not for a saved jam as it was)
        self.guided = False
        self.listening = False                  # hearing your melody
        super().__init__(*args, **kwargs)

    def words(self) -> Words:
        lang = self.lang
        if lang not in self._words:
            self._words[lang] = Words(SKILL_ROOT / "locale", lang)
        return self._words[lang]

    @property
    def jams(self) -> Jams:
        try:
            folder = Path(self.file_system.path) / "jams"
        except Exception:
            folder = Path.home() / ".local/share/ovos-skill-jamband/jams"
        return Jams(folder, SKILL_ROOT / "jams")

    # ------------------------------------------------------------ starting
    def _band(self):
        """ovos-phal-plugin-midi's status, or None when it doesn't answer."""
        r = self.bus.wait_for_response(Message("ovos.midi.status"), "ovos.midi.status.response",
                                       timeout=MIDI_WAIT)
        if r is None or r.data.get("engine") in (None, "none"):
            return None
        return r.data

    def _new_jam(self, band, state=None, script=None) -> Jam:
        self.stop()
        with self._lock:
            self.jam = Jam(self._send, self.skill_id, float(band.get("latency", 0.3)), on_bar=self._on_bar,
                           state=state, script=script)
            self.jam.on_end = lambda jam=self.jam: self._ended(jam)
        self.playing_name = ""
        self.offer_save = True
        self.guided = False
        return self.jam

    @intent_handler("jam.intent")
    def handle_jam(self, message):
        utterance = message.data.get("query") or message.data.get("utterance", "")
        band = self._band()
        if not band:
            self.speak_dialog("no_midi")
            return
        w = self.words()
        style = STYLES[w.style(utterance) or DEFAULT]
        jam = self._new_jam(band)
        change = {"style": style}
        key = w.key(utterance)
        if key:
            change["key"] = key
        tempo = w.tempo(utterance)
        if tempo:
            change["tempo"] = tempo
        jam.change(**change)
        if w.has(utterance, "intro"):
            jam.intro()
        jam.start()
        self._keep_active()
        parts = w.parts(utterance)
        tune = T.find(utterance)
        if tune:
            if parts:
                jam.add(*parts)
            self._use_tune(tune)
        elif parts:
            self._add(parts)
        else:
            self.speak_dialog("start", {"style": style.name, "key": w.spoken_key(jam.state.key)},
                              expect_response=True)

    @intent_handler("guided.intent")
    def handle_guided(self, message):
        if not self._band():
            self.speak_dialog("no_midi")
            return
        self.stop()
        self._ask("style", "guide_style", tries=2)

    @intent_handler("melody.intent")
    def handle_melody(self, message):
        utterance = message.data.get("utterance", "")
        band = self._band()
        if not band:
            self.speak_dialog("no_midi")
            return
        mel = self.words().notes(message.data.get("notes") or utterance, strict=False)
        self._melody(mel, band)

    @intent_handler("play_saved.intent")
    def handle_play_saved(self, message):
        name = message.data.get("name", "")
        found = self.jams.find(name) if name else self.jams.latest()
        if not found:
            self._say_list("not_found", {"name": name})
            return
        band = self._band()
        if not band:
            self.speak_dialog("no_midi")
            return
        title = self._title(found)
        jam = self._new_jam(band, State.from_dict(found["first"]), found.get("log"))
        self.playing_name = title
        self.offer_save = False
        self.speak_dialog("playing", {"name": title}, wait=True)
        jam.start()
        self._keep_active()

    @intent_handler("surprise.intent")
    def handle_surprise(self, message):
        band = self._band()
        if not band:
            self.speak_dialog("no_midi")
            return
        w = self.words()
        rec = compose(style_name=w.style(message.data.get("utterance", "")),
                      tune_id=T.find(message.data.get("utterance", "")))
        jam = self._new_jam(band, State.from_dict(rec["first"]), rec["log"])
        tune = T.title(rec["tune"], self.lang)
        self.playing_name = f"{tune} · {rec['style']}"
        soloists = [self._name(p) for p in rec["soloists"]]
        self.speak_dialog("surprise", {"tune": tune, "style": rec["style"], "soloists": self._join(soloists)},
                          wait=True)
        jam.start()
        self._keep_active()

    @intent_handler("list_tunes.intent")
    def handle_tunes(self, message):
        names = [T.title(t, self.lang) for t in T.every()]
        random.shuffle(names)
        self.speak_dialog("tunes", {"names": self._join(names[:8]), "count": len(names)})

    @intent_handler("list_jams.intent")
    def handle_list(self, message):
        self._say_list("list")

    @intent_handler("delete_jam.intent")
    def handle_delete(self, message):
        name = message.data.get("name", "")
        found = self.jams.find(name)
        if not found:
            self._say_list("not_found", {"name": name})
        elif found.get("bundled"):
            self.speak_dialog("cant_delete", {"name": self._title(found)})
        else:
            self._ask("delete", "delete_ask", {"name": found["name"]}, name=found["name"])

    def _say_list(self, dialog: str, data: dict | None = None):
        names = [self._title(d) for d in self.jams.all()]
        data = dict(data or {})
        data["names"] = self._join(names[:8])
        data["count"] = len(names)
        self.speak_dialog(dialog if names or dialog != "list" else "list_empty", data)

    def _title(self, saved: dict) -> str:
        """A saved jam's name; the ones that come with the skill have one per language."""
        names = saved.get("names") or {}
        lang = self.lang.split("-")[0].lower()
        return names.get(lang) or names.get("en") or saved.get("name", "")

    def _join(self, names: list) -> str:
        if len(names) < 2:
            return "".join(names)
        word = (self.words().voc.get("and_word") or ["and"])[-1]
        return ", ".join(names[:-1]) + f" {word} " + names[-1]

    # ------------------------------------------------------------ questions
    def _ask(self, what: str, dialog: str, data: dict | None = None, **more):
        self.asking = {"what": what, "until": time.time() + ANSWER_WAIT, **more}
        self.speak_dialog(dialog, data or {}, expect_response=True)
        self._keep_active()

    def _asked(self):
        a = self.asking
        if a and time.time() > a["until"]:
            self.asking = a = None
        return a

    def answer(self, utterance: str) -> bool:
        """The answer to what Emkay asked; False when it isn't one (then it may be a command)."""
        a = self._asked()
        w = self.words()
        yes, no = w.has(utterance, "yes"), w.has(utterance, "no")
        what = a["what"]
        if what == "style":
            style = w.style(utterance)
            if not style and (w.has(utterance, "you_choose") or a.get("tries", 1) <= 1):
                style = random.choice(list(STYLES))
            if not style:
                self._ask("style", "guide_style_again", tries=a.get("tries", 1) - 1)
                return True
            self._ask("key", "guide_key", {"style": style}, style=style)
            return True
        if what == "key":
            band = self._band()
            if not band:
                self.asking = None
                self.speak_dialog("no_midi")
                return True
            style = STYLES[a["style"]]
            key = w.key(utterance) or w.bare_key(utterance)
            if not key and w.has(utterance, "minor"):
                key = M.Key(style.key.tonic, True)
            jam = self._new_jam(band)
            jam.change(style=style, **({"key": key} if key else {}))
            self.guided = True
            first = style.band[0]
            jam.add(first)
            jam.start()
            self.asking = None
            self._next_part(intro=True)
            return True
        if what == "next_part":
            if no:
                self.asking = None
                self.guided = False
                self.speak_dialog("guide_free", expect_response=True)
                return True
            if yes:
                self.asking = None
                self._add([a["part"]])
                return True
            return False
        if what == "save":
            if yes:
                self._ask("name", "save_name", recording=a.get("recording"))
                return True
            if no:
                self.asking = None
                self.speak_dialog("ok")
                return True
            return False
        if what == "name":
            name = utterance.strip().strip(".!?")
            if not name:
                return False
            self.asking = None
            self._save(name, a.get("recording"))
            return True
        if what == "delete":
            self.asking = None
            if yes:
                self.jams.delete(a["name"])
                self.speak_dialog("deleted", {"name": a["name"]})
            else:
                self.speak_dialog("ok")
            return True
        return False

    def _next_part(self, intro=False):
        """Guided: offer the next instrument of the style's band."""
        jam = self.jam
        if not jam:
            return
        missing = [p for p in jam.state.style.band if p not in jam.state.parts]
        if not missing:
            self.guided = False
            self.speak_dialog("guide_done", expect_response=True)
            return
        part = missing[0]
        data = {"part": self._name(part), "first": self._name(jam.state.parts[0]) if jam.state.parts else "",
                "style": jam.state.style.name, "key": self.words().spoken_key(jam.state.key)}
        self._ask("next_part", "guide_first" if intro else "guide_next", data, part=part)

    # ------------------------------------------------------------ while it plays
    def can_converse(self, message=None) -> bool:
        """OVOS asks first: is this sentence for the band?"""
        utterances = (message.data.get("utterances") if message else None) or []
        if self._asked():
            return True
        if not self.jam or not self.jam.running:
            return False
        return not utterances or any(self.understand(u) for u in utterances)

    def converse(self, message=None):
        if message is None:
            return False
        for utterance in message.data.get("utterances") or []:
            if self._asked() and self.answer(utterance):
                return True
            if not self.jam or not self.jam.running:
                continue
            action = self.understand(utterance)
            if action:
                self.asking = None
                if self.jam.take_over():
                    self.speak_dialog("take_over")
                    self.playing_name = ""
                    self.offer_save = True        # changed: a new jam, to save if you like
                self.do(*action)
                return True
        return False

    def understand(self, utterance: str):
        """What `utterance` asks of the band: (what, value), or None."""
        w, st = self.words(), self.jam.state
        if w.has(utterance, "save"):
            return ("save", self._name_in(utterance))
        if w.has(utterance, "finish"):
            return ("finish", None)
        tune = T.find(utterance)
        if tune:
            return ("tune", tune)
        notes = w.notes(utterance)
        if notes:
            return ("notes", notes)
        parts = w.parts(utterance)
        if w.has(utterance, "melody"):
            if parts and w.has(utterance, "on"):
                return ("lead", parts[0])
            return ("melody", w.notes(utterance, strict=False))
        if w.has(utterance, "solo"):
            return ("solo", parts[0] if parts else None)
        if w.has(utterance, "break"):
            return ("break", None)
        if w.has(utterance, "top"):
            return ("top", None)
        if w.has(utterance, "intro"):
            return ("intro", None)
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
        if self.guided and (w.has(utterance, "yes")):
            missing = [p for p in st.style.band if p not in st.parts]
            if missing:
                return ("add", missing[:1])
        return None

    def _name_in(self, utterance: str) -> str:
        """"save it as Friday blues" -> "Friday blues" (the words after "as")."""
        w = self.words()
        low = utterance.lower()
        for word in sorted(w.voc.get("as_word", []), key=len, reverse=True):
            i = low.find(f" {word} ")
            if i >= 0:
                return utterance[i + len(word) + 2:].strip().strip(".!?")
        return ""

    def do(self, what, value):
        w, jam = self.words(), self.jam
        if what == "finish":
            self._finish()
        elif what == "save":
            if value:
                self._save(value, jam.recording())
            else:
                self._ask("name", "save_name", recording=jam.recording())
        elif what == "notes":
            self._use_melody(value)
        elif what == "tune":
            self._use_tune(value)
        elif what == "melody":
            if value:
                self._use_melody(value)
            else:
                threading.Thread(target=self._hear_melody, daemon=True).start()
        elif what == "lead":
            jam.change(lead=value)
            self.speak_dialog("lead", {"part": self._name(value)}, expect_response=True)
        elif what == "solo":
            part = value or (jam.state.lead if jam.state.melody else SOLOIST.get(jam.state.style.name, "sax"))
            jam.solo_for(part)
            self.speak_dialog("solo", {"part": self._name(part)}, expect_response=True)
        elif what == "break":
            jam.brk()
            self.speak_dialog("break", expect_response=True)
        elif what == "top":
            jam.from_the_top()
            self.speak_dialog("top", expect_response=True)
        elif what == "intro":
            jam.intro()
            self.speak_dialog("intro", expect_response=True)
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
            if jam.state.melody:     # your melody moves with it
                semis = (value.tonic - jam.state.key.tonic + 6) % 12 - 6
                mel = jam.state.melody.transposed(semis)
                jam.change(key=value, melody=mel, chords=self._chords(mel, value))
            else:
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
        if self.guided:
            self.speak_dialog(comment, wait=True)
            self._next_part()
        else:
            self.speak_dialog(comment, expect_response=True)

    def _name(self, part: str) -> str:
        return self.dialog_renderer.render(f"name_{part}", {}) if self.dialog_renderer else part

    def _finish(self):
        """A big last chord on the next bar line (then _ended)."""
        self.jam.finish()

    def _ended(self, jam):
        """The last chord has rung: thanks - and an offer to save the jam."""
        if self.jam is not jam:
            return
        self.jam = None
        self.gui.release()
        rec = jam.recording()
        if self.offer_save and rec["bars"] >= SAVE_AFTER_BARS:
            self.speak_dialog("the_end", wait=True)
            self._ask("save", "save_ask", recording=rec)
        else:
            self.speak_dialog("the_end")
        self.playing_name = ""

    def _save(self, name: str, recording: dict | None):
        if not recording:
            self.speak_dialog("ok")
            return
        self.jams.save(name, recording, lang=self.lang)
        self.speak_dialog("saved", {"name": name}, expect_response=bool(self.jam and self.jam.running))

    # ------------------------------------------------------------ your melody
    def _chords(self, mel: M.Melody, key) -> list:
        style = self.jam.state.style.name if self.jam else DEFAULT
        return [key.chord(d) for d in M.fit_chords(mel, key, style)]

    def _use_melody(self, mel: M.Melody, key=None, chords=None, tune: str = ""):
        """The band plays `mel`: in its key, with chords that suit it, the lead on top."""
        jam = self.jam
        key = key or M.key_of(mel.notes)
        lead = jam.state.lead if jam.state.melody else LEADS.get(jam.state.style.name, "piano")
        jam.change(melody=mel, key=key, chords=chords or self._chords(mel, key), lead=lead)
        if not any(p in jam.state.parts for p in ("bass", "piano", "guitar", "organ", "bandoneon")):
            jam.add(*[p for p in jam.state.style.band[:3] if p not in jam.state.parts])
        jam.intro()
        if tune:
            self.speak_dialog("tune", {"tune": tune, "style": jam.state.style.name, "part": self._name(lead)},
                              expect_response=True)
        else:
            self.speak_dialog("got_melody", {"count": len(mel.notes), "key": self.words().spoken_key(key),
                                             "part": self._name(lead)}, expect_response=True)

    def _use_tune(self, tune_id: str):
        mel, key = T.melody(tune_id), T.key(tune_id)
        chords = chords_for(tune_id, mel, key, self.jam.state.style.name)
        self._use_melody(mel, key, chords, T.title(tune_id, self.lang))

    def _melody(self, mel, band):
        """From the melody intent: notes said, or hum/play them now; then a jam around it."""
        if not self.jam or not self.jam.running:
            jam = self._new_jam(band)
            jam.change(style=STYLES[DEFAULT])
            jam.start()
            self._keep_active()
        if mel:
            self._use_melody(mel)
        else:
            self._hear_melody()

    def _hear_melody(self):
        """Quiet, please: Emkay listens to your humming (or your keyboard)."""
        jam = self.jam
        if not jam or self.listening:
            return
        self.listening = True
        try:
            jam.silent(True)
            self.speak_dialog("hum_now", wait=True)
            mel, _tempo, key = Listen(self.bus).hear(jam.state.tempo)
            jam.silent(False)
            if mel and len(mel.notes) >= 2:
                self._use_melody(mel, key)
            else:
                self.speak_dialog("didnt_hear", expect_response=True)
        finally:
            self.listening = False
            if jam:
                jam.silent(False)

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
        pos = jam.position(bar)
        upcoming = [prog[(pos + k) % len(prog)] for k in range(1, 5)]
        names = {p: self._name(p) for p in PARTS}
        title = f"{st.style.name.title()} · {st.key.name} · {st.tempo} bpm"
        if self.playing_name:
            title = f"▶ {self.playing_name} · " + title
        note = ""
        if jam.soloing:
            note = f"SOLO · {names.get(jam.soloing, jam.soloing)}"
        elif bar == jam.break_bar:
            note = "BREAK"
        elif st.melody and bar >= jam.quiet_until:
            note = f"♪ {names.get(st.lead, st.lead)}"
        self.gui["image"] = screen.render(title, chord, upcoming, st.parts, names, note)
        if bar == 0:
            self.gui["title"] = ""
            self.gui["caption"] = ""
            self.gui["fill"] = "PreserveAspectFit"
            self.gui["background_color"] = screen.BG
            self.gui.show_page("SYSTEM_ImageFrame", override_idle=True)

    def stop(self):
        with self._lock:
            jam, self.jam = self.jam, None
        self.playing_name = ""
        self.offer_save = True
        self.guided = False
        if jam is None:
            return False
        jam.stop()
        self.gui.release()
        return True
