"""Hearing your melody: hummed into the microphone, or played on a MIDI keyboard.

The microphone is the listener's: OVOS' recording mode (ovos-dinkum-listener;
Emkay does the same) - recognizer_loop:state.set {"state": "recording",
"recording_name": ...} records until it is quiet, or until
recognizer_loop:record_stop, then writes <listener save_path>/recordings/<name>.wav
and says recognizer_loop:record_end. Meanwhile the keys pressed on a MIDI
keyboard come as ovos.midi.input (ovos-phal-plugin-midi): when they do,
the keyboard wins and the recording is stopped once you stop playing.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from ovos_bus_client.message import Message

from . import melody as M

LONGEST = 14.0          # seconds of humming at most
KEYS_DONE = 2.0         # this long after the last key, the keyboard melody is done


def recordings_folder() -> Path:
    try:
        from ovos_config import Configuration
        from ovos_config.locations import get_xdg_data_save_path
        listener = Configuration().get("listener", {})
        return Path(listener.get("save_path") or f"{get_xdg_data_save_path()}/listener") / "recordings"
    except Exception:
        return Path.home() / ".local/share/mycroft/listener/recordings"


class Listen:
    """One go at hearing a melody: Listen(bus).hear(tempo) -> (Melody, tempo, Key) or (None, ...)."""

    def __init__(self, bus, folder: Path | None = None):
        self.bus = bus
        self.folder = folder or recordings_folder()
        self.keys: list = []
        self.last_key = 0.0
        self.ended = threading.Event()

    def _on_key(self, message):
        d = message.data or {}
        kind = d.get("type")
        if kind == "note_on" and d.get("velocity", 0) > 0:
            self.keys.append((time.time(), "on", d.get("note")))
        elif kind in ("note_off", "note_on"):
            self.keys.append((time.time(), "off", d.get("note")))
        else:
            return
        self.last_key = time.time()

    def _on_end(self, _message=None):
        self.ended.set()

    def hear(self, tempo: int | None = None, bar_start: float | None = None):
        name = f"jamband-{int(time.time() * 1000)}"
        self.bus.on("ovos.midi.input", self._on_key)
        self.bus.on("recognizer_loop:record_end", self._on_end)
        try:
            self.bus.emit(Message("recognizer_loop:state.set", {"state": "recording", "recording_name": name}))
            t0 = time.time()
            stopped = False
            while time.time() - t0 < LONGEST + 4:
                if self.ended.wait(0.1):
                    break
                keyboard_done = self.keys and time.time() - self.last_key > KEYS_DONE
                if not stopped and (keyboard_done or time.time() - t0 > LONGEST):
                    self.bus.emit(Message("recognizer_loop:record_stop"))
                    stopped = True
        finally:
            self.bus.remove("ovos.midi.input", self._on_key)
            self.bus.remove("recognizer_loop:record_end", self._on_end)
        if self.keys:
            mel = M.from_played(self.keys, tempo or 100)
            return mel, tempo or 100, M.key_of(mel.notes) if mel else None
        wav = self.folder / f"{name}.wav"
        for _ in range(30):                      # written just before record_end, or just after
            if wav.exists():
                break
            time.sleep(0.1)
        if not wav.exists():
            return None, tempo, None
        try:
            x, sr = M.wav_samples(wav)
            return M.from_audio(x, sr, tempo)
        finally:
            for p in (wav, wav.with_suffix(".json")):
                try:
                    p.unlink()
                except OSError:
                    pass
