import wave

import numpy as np

from ovos_skill_jamband.listen import Listen
from conftest import hum


class Bus:
    """The listener's recording mode, as ovos-dinkum-listener does it: writes the WAV, says record_end."""

    def __init__(self, folder, audio=None, keys=()):
        self.handlers, self.folder, self.audio, self.keys = {}, folder, audio, keys

    def on(self, t, f):
        self.handlers.setdefault(t, []).append(f)

    def remove(self, t, f):
        self.handlers.get(t, []).remove(f)

    def emit(self, m):
        if m.msg_type == "recognizer_loop:state.set" and self.audio is not None:
            x, sr = self.audio
            self.folder.mkdir(parents=True, exist_ok=True)
            with wave.open(str(self.folder / f"{m.data['recording_name']}.wav"), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes((np.clip(x, -1, 1) * 32000).astype("<i2").tobytes())
            for f in self.handlers.get("recognizer_loop:record_end", []):
                f(None)


def test_hummed_into_the_listener(tmp_path):
    bus = Bus(tmp_path, hum([62, 64, 66, 67, 69, 62]))
    mel, tempo, key = Listen(bus, tmp_path).hear(100)
    assert [p % 12 for p in mel.pitches()] == [2, 4, 6, 7, 9, 2] and key.tonic == 2
    assert not list(tmp_path.glob("*.wav"))                 # cleaned up
