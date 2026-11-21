"""The package is installed (pip install -e .), so the modules are imported
as ovos_skill_jamband.*."""
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def hum(pitches, tempo=100, sr=16000, flat=0.3):
    """A hummed tune: a voice-like tone a bit flat, with vibrato and noise, a beat a note."""
    beat = 60 / tempo
    out = [np.zeros(3000)]
    for p in pitches:
        n = int(beat * sr * 0.88)
        t = np.arange(n) / sr
        f = 440 * 2 ** ((p - flat - 69) / 12) * (1 + 0.006 * np.sin(2 * np.pi * 5.5 * t))
        ph = 2 * np.pi * np.cumsum(f) / sr
        env = np.minimum(1, np.minimum(t / 0.03, (n / sr - t) / 0.05))
        out += [(0.5 * np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.1 * np.sin(3 * ph)) * env, np.zeros(int(beat * sr * 0.12))]
    x = np.concatenate(out)
    return x + 0.01 * np.random.default_rng(1).standard_normal(len(x)), sr
