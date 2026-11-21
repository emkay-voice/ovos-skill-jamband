"""Your melody: said, played or hummed, and the chords that go with it.

A melody is notes on a beat grid: (beat, MIDI pitch, beats), four beats a
bar. It comes from

  - words: "C D E C" or "do re mi do", in the language's note names
    (from_names) - a beat each;
  - a MIDI keyboard: the plugin's ovos.midi.input, timed and put on the
    grid (from_played);
  - humming: a recording, its pitch followed frame by frame (YIN), cut
    into notes, tuned to the key it is in and put on the grid (from_audio).

fit_chords() then finds a chord a bar that suits the melody (and the
style): the jam plays your melody with the band under it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .music import Chord, Key

#: what a bar of the melody is cut to: eighth notes
GRID = 0.5

# Krumhansl-Kessler key profiles
_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


@dataclass
class Melody:
    notes: list = field(default_factory=list)      # [(beat, pitch, beats)]
    bars: int = 1

    @property
    def beats(self) -> int:
        return self.bars * 4

    def in_bar(self, bar: int) -> list:
        """The notes of bar `bar` (0-based, the melody repeats): (beat in bar, pitch, beats)."""
        b = bar % self.bars
        return [(beat - 4 * b, p, d) for beat, p, d in self.notes if 4 * b <= beat < 4 * b + 4]

    def transposed(self, semis: int) -> "Melody":
        return Melody([(b, p + semis, d) for b, p, d in self.notes], self.bars)

    def pitches(self) -> list[int]:
        return [p for _, p, _ in self.notes]

    def to_dict(self) -> dict:
        return {"notes": [list(n) for n in self.notes], "bars": self.bars}

    @classmethod
    def from_dict(cls, d: dict) -> "Melody":
        return cls([tuple(n) for n in d.get("notes", [])], int(d.get("bars", 1)))

    @classmethod
    def of(cls, notes: list) -> "Melody | None":
        """A melody of `notes` [(beat, pitch, beats)], starting on beat 0 and
        lasting whole bars (the last note held to the bar line)."""
        notes = sorted((float(b), int(p), float(d)) for b, p, d in notes if d > 0)
        if not notes:
            return None
        first = notes[0][0]
        notes = [(b - first, p, d) for b, p, d in notes]
        end = max(b + d for b, _, d in notes)
        bars = max(1, math.ceil(end / 4 - 1e-6))
        if bars == 3:                     # phrases come in 1, 2, 4 or 8 bars
            bars = 4
        elif 4 < bars < 8:
            bars = 8
        b, p, d = notes[-1]
        notes[-1] = (b, p, max(d, min(4 * bars - b, 4.0)))
        return cls(notes, bars)


# ------------------------------------------------------------------ keys
def key_of(notes: list) -> Key:
    """The key the notes are most likely in (Krumhansl-Schmuckler),
    weighting each pitch by how long it sounds."""
    weight = [0.0] * 12
    for _, p, d in notes:
        weight[p % 12] += max(0.25, d)
    best, best_r = Key(0), -2.0
    last = notes[-1][1] % 12 if notes else None
    for tonic in range(12):
        for minor, profile in ((False, _MAJOR), (True, _MINOR)):
            prof = profile[-tonic:] + profile[:-tonic] if tonic else profile
            r = float(np.corrcoef(weight, prof)[0, 1]) if any(weight) else 0.0
            if minor:
                r -= 0.02           # a tie goes to major
            if last == tonic:       # a tune usually ends at home
                r += 0.12
            if r > best_r:
                best, best_r = Key(tonic, minor), r
    return best


def place(pcs: list[int], start: int = 60) -> list[int]:
    """Pitch classes as a tune: each note the nearest to the one before
    (up or down a fourth at most), starting near `start`."""
    out, prev = [], start
    for pc in pcs:
        p = prev + ((pc - prev) % 12)
        if p - prev > 6:
            p -= 12
        out.append(p)
        prev = p
    # keep it in a singable range
    shift = 0
    while min(out) + shift < 55:
        shift += 12
    while max(out) + shift > 84:
        shift -= 12
    return [p + shift for p in out]


# ------------------------------------------------------------------ said
def from_names(tokens: list, note_of, rest_words=()) -> Melody | None:
    """A melody from note names, a beat each: `note_of(token, following)`
    gives (pitch class, words used) or (None, 0), as words.note does.
    A rest word ("pause", "rest") is a beat of silence; "long" holds the
    note before one more beat."""
    pcs, beats, i = [], [], 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in rest_words:
            pcs.append(None)
            beats.append(1.0)
            i += 1
            continue
        pc, used = note_of(tok, " ".join(tokens[i + 1:i + 3]))
        if pc is not None:
            pcs.append(pc)
            beats.append(1.0)
            i += 1 + used
        else:
            i += 1
    if sum(1 for p in pcs if p is not None) < 2:
        return None
    pitches = iter(place([p for p in pcs if p is not None]))
    notes, beat = [], 0.0
    for pc, d in zip(pcs, beats):
        if pc is not None:
            notes.append((beat, next(pitches), d * 0.95))
        beat += d
    return Melody.of(notes)


# ------------------------------------------------------------------ played
def from_played(events: list, tempo: int, start: float | None = None) -> Melody | None:
    """A melody from keys pressed: `events` are (time, "on"/"off", note).
    `start` is a bar line (the jam's), else the first note starts the melody."""
    held, notes = {}, []
    for t, kind, n in sorted(events, key=lambda e: e[0]):
        if kind == "on":
            held.setdefault(n, t)
        elif n in held:
            notes.append((held.pop(n), n, t))
    last = max((e[0] for e in events), default=0)
    for n, t0 in held.items():
        notes.append((t0, n, last + 0.3))
    if not notes:
        return None
    notes.sort()
    beat = 60.0 / tempo
    t0 = start if start is not None else notes[0][0]
    out = []
    for on, n, off in notes:
        b = snap((on - t0) / beat)
        d = max(GRID, snap((off - on) / beat))
        if out and out[-1][0] == b:          # a chord: the top note is the tune
            if n > out[-1][1]:
                out[-1] = (b, n, d)
            continue
        out.append((b, n, d))
    if start is not None:                    # drop whole empty bars before it
        skip = 4 * int(out[0][0] // 4)
        out = [(b - skip, n, d) for b, n, d in out]
        return _from_bar(out)
    return Melody.of(_legato(out))


def _from_bar(notes):
    m = Melody.of(_legato(notes))
    if m and notes and notes[0][0] > 0:      # Melody.of moved it to beat 0: keep the pickup's place
        first = notes[0][0]
        m = Melody([(b + first, p, d) for b, p, d in m.notes], m.bars)
        end = max(b + d for b, _, d in m.notes)
        m.bars = max(m.bars, math.ceil(end / 4 - 1e-6))
    return m


def snap(beats: float) -> float:
    return round(beats / GRID) * GRID


def _legato(notes):
    """No overlaps; each note at most up to the next."""
    out = []
    for i, (b, p, d) in enumerate(notes):
        if i + 1 < len(notes):
            d = min(d, notes[i + 1][0] - b)
        if d > 0:
            out.append((b, p, d))
    return out


# ------------------------------------------------------------------ hummed
def pitch_track(x: np.ndarray, sr: int, hop: float = 0.01, fmin: float = 70.0,
                fmax: float = 1000.0, threshold: float = 0.15):
    """(frame times, f0 in Hz or 0 where unvoiced, RMS) by YIN."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim > 1:
        x = x.mean(axis=1)
    peak = np.max(np.abs(x)) if x.size else 0
    if peak <= 0:
        return np.zeros(0), np.zeros(0), np.zeros(0)
    x = x / peak
    w = int(sr * 0.04)                       # 40 ms window: down to ~70 Hz
    h = max(1, int(sr * hop))
    tmin, tmax = max(2, int(sr / fmax)), min(w - 1, int(sr / fmin))
    n = 1 + max(0, (len(x) - 2 * w) // h)
    times, f0, rms = np.zeros(n), np.zeros(n), np.zeros(n)
    size = 1 << int(np.ceil(np.log2(2 * w)))
    for i in range(n):
        frame = x[i * h:i * h + 2 * w]
        if len(frame) < 2 * w:
            break
        times[i] = (i * h + w) / sr
        a = frame[:w]
        rms[i] = math.sqrt(float(np.mean(a * a)))
        # difference function via FFT cross-correlation
        F = np.fft.rfft(frame, size)
        A = np.fft.rfft(a[::-1], size)
        corr = np.fft.irfft(F * A, size)[w - 1:w - 1 + tmax + 1]
        cum = np.cumsum(frame * frame)
        energy_a = cum[w - 1]
        taus = np.arange(tmax + 1)
        e_shift = cum[taus + w - 1] - np.concatenate(([0.0], cum[:tmax]))
        d = energy_a + e_shift - 2 * corr
        d[0] = 0
        cmnd = np.ones_like(d)
        running = np.cumsum(d[1:])
        cmnd[1:] = d[1:] * np.arange(1, tmax + 1) / np.where(running == 0, 1, running)
        tau = None
        for t in range(tmin, tmax):
            if cmnd[t] < threshold:
                while t + 1 < tmax and cmnd[t + 1] < cmnd[t]:
                    t += 1
                tau = t
                break
        if tau is None:
            continue
        # parabolic interpolation
        if 0 < tau < tmax:
            s0, s1, s2 = cmnd[tau - 1], cmnd[tau], cmnd[tau + 1]
            denom = s0 + s2 - 2 * s1
            shift = 0.5 * (s0 - s2) / denom if denom else 0.0
        else:
            shift = 0.0
        f0[i] = sr / (tau + shift)
    return times, f0, rms


def notes_from_track(times, f0, rms, min_note: float = 0.09):
    """[(start s, end s, midi float)]: voiced, loud enough, stable stretches."""
    if len(times) == 0:
        return []
    loud = rms > max(0.02, 0.12 * float(np.max(rms)))
    midi = np.where((f0 > 0) & loud, 69 + 12 * np.log2(np.maximum(f0, 1e-6) / 440.0), np.nan)
    # a 5-frame median: octave jumps and glitches go
    m = midi.copy()
    for i in range(len(midi)):
        win = midi[max(0, i - 2):i + 3]
        win = win[~np.isnan(win)]
        m[i] = np.median(win) if len(win) >= 3 and not np.isnan(midi[i]) else np.nan
    hop = times[1] - times[0] if len(times) > 1 else 0.01
    spans, start, vals = [], None, []        # (first frame, frame after, midi)

    def close(i):
        if start is not None and (i - start) * hop >= min_note:
            spans.append((start, i))

    for i, v in enumerate(m):
        if np.isnan(v):
            close(i)
            start, vals = None, []
            continue
        # a new note: the pitch moved more than 0.6 semitone from this note's
        if start is None or abs(v - np.median(vals)) > 0.6 and _stays(m, i, v):
            close(i)
            start, vals = i, []
        vals.append(v)
    close(len(m))
    notes = []
    min_frames = max(2, int(min_note / hop))
    for a, b in spans:
        for a2, b2 in _syllables(rms, a, b, min_frames):
            seg = m[a2:b2]
            seg = seg[~np.isnan(seg)]
            if len(seg):
                notes.append((times[a2] - hop / 2, times[b2 - 1] + hop / 2, float(np.median(seg))))
    return _octaves(notes)


def _syllables(rms, a, b, min_frames):
    """A stretch on one pitch cut where the sound dips between two louder
    parts: the same note sung again on a new syllable."""
    r = np.convolve(rms[a:b], np.ones(3) / 3, mode="same")
    cuts = [0]
    i = min_frames
    while i < len(r) - min_frames:
        left, right = r[cuts[-1]:i].max(), r[i:].max() if i < len(r) else 0
        if r[i] < 0.6 * min(left, right) and r[i] == r[max(0, i - 3):i + 4].min():
            cuts.append(i)
            i += min_frames
        else:
            i += 1
    cuts.append(len(r))
    return [(a + x, a + y) for x, y in zip(cuts, cuts[1:]) if y - x >= min_frames]


def _octaves(notes):
    """A note an octave off from both its neighbours is the pitch tracker's
    mistake (it caught a harmonic): put it back."""
    out = list(notes)
    for i, (s, e, p) in enumerate(out):
        near = [out[j][2] for j in (i - 1, i + 1) if 0 <= j < len(out)]
        if not near:
            continue
        for shift in (-12, 12):
            if all(abs(p - q) > 7 for q in near) and all(abs(p + shift - q) <= 7 for q in near):
                out[i] = (s, e, p + shift)
                break
    return out


def _stays(m, i, v, frames=4):
    """The pitch stays near `v` for a few frames (not a slide through it)."""
    ahead = m[i:i + frames]
    ahead = ahead[~np.isnan(ahead)]
    return len(ahead) >= min(frames, 2) and np.all(np.abs(ahead - v) < 0.8)


def tune(raw: list) -> tuple[list, Key]:
    """Raw hummed notes [(start, end, midi float)] -> [(start, end, pitch)]
    in the key they are in: first the singer's own tuning (how far the
    whole tune sits between semitones), then each note to the key's scale
    when it is nearer to it than to a note outside."""
    if not raw:
        return [], Key(0)
    devs = [m - round(m) for _, _, m in raw]
    weights = [e - s for s, e, _ in raw]
    angle = math.atan2(sum(w * math.sin(2 * math.pi * d) for w, d in zip(weights, devs)),
                       sum(w * math.cos(2 * math.pi * d) for w, d in zip(weights, devs)))
    offset = angle / (2 * math.pi)
    rounded = [(s, e, int(round(m - offset)), m - offset) for s, e, m in raw]
    key = key_of([(0, p, e - s) for s, e, p, _ in rounded])
    scale = set(key.scale())
    out = []
    for s, e, p, exact in rounded:
        if p % 12 not in scale:
            other = p + (1 if exact > p else -1)
            if other % 12 in scale and abs(exact - p) > 0.25:
                p = other
        out.append((s, e, p))
    return out, key


def estimate_tempo(onsets: list, lo: int = 60, hi: int = 160) -> int:
    """The tempo whose eighth-note grid the onsets fit best."""
    if len(onsets) < 3:
        return 100
    t = np.asarray(onsets) - onsets[0]
    best, best_err = 100, 1e9
    for bpm in range(lo, hi + 1, 2):
        g = 30.0 / bpm                       # an eighth note
        err = float(np.mean(np.abs(t / g - np.round(t / g)))) + 0.002 * abs(bpm - 100) / 40
        if err < best_err:
            best, best_err = bpm, err
    return best


def from_audio(x, sr: int, tempo: int | None = None) -> tuple[Melody | None, int, Key | None]:
    """A hummed (sung, whistled) melody: (melody, tempo, key)."""
    times, f0, rms = pitch_track(x, sr)
    raw = notes_from_track(times, f0, rms)
    if len(raw) < 2:
        return None, tempo or 100, None
    tuned, key = tune(raw)
    tempo = tempo or estimate_tempo([s for s, _, _ in tuned])
    beat = 60.0 / tempo
    t0 = tuned[0][0]
    notes = []
    for s, e, p in tuned:
        b = snap((s - t0) / beat)
        d = max(GRID, snap((e - s) / beat))
        if notes and notes[-1][0] == b:
            continue
        notes.append((b, p, d))
    notes = _legato(notes)
    # in a range an instrument plays it well
    mid = sorted(p for _, p, _ in notes)[len(notes) // 2]
    shift = 12 * round((67 - mid) / 12)
    notes = [(b, p + shift, d) for b, p, d in notes]
    return Melody.of(notes), tempo, key


def wav_samples(path: str):
    """(float samples, rate) of a 16-bit WAV."""
    import wave
    with wave.open(str(path), "rb") as w:
        sr, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        data = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError("16-bit WAV only")
    x = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


# ------------------------------------------------------------------ chords
#: the chords a melody can get, by mode: (degree, how common)
_CANDIDATES = {
    "major": [("I", 1.0), ("IV", 0.8), ("V7", 0.8), ("vi", 0.6), ("ii7", 0.5), ("iii", 0.2), ("V", 0.4)],
    "minor": [("i", 1.0), ("iv", 0.8), ("V7", 0.8), ("VI", 0.5), ("VII", 0.4), ("iv7", 0.2), ("v", 0.2)],
    "blues": [("I7", 1.0), ("IV7", 0.9), ("V7", 0.8)],
}
#: a chord that follows another well
_MOVES = {("V7", "I"), ("V", "I"), ("IV", "I"), ("IV", "V7"), ("ii7", "V7"), ("vi", "ii7"), ("vi", "IV"),
          ("I", "IV"), ("I", "V7"), ("I", "vi"), ("V7", "i"), ("iv", "V7"), ("iv", "i"), ("VI", "VII"),
          ("VII", "i"), ("i", "iv"), ("i", "VI"), ("VI", "V7"), ("I7", "IV7"), ("IV7", "I7"),
          ("V7", "IV7"), ("V7", "I7"), ("I", "ii7"), ("i", "V7")}


def fit_chords(melody: Melody, key: Key, style_name: str = "") -> list[str]:
    """A chord a bar (as degrees of `key`) that suits the melody: its long
    notes and the notes on the beat should be chord notes. The first bar
    is the home chord; chords that usually follow one another are favoured
    (the melody repeats, so the last bar leads back to the first)."""
    mode = "minor" if key.minor else ("blues" if style_name in ("blues",) else "major")
    cands = _CANDIDATES[mode]
    home = cands[0][0]
    bars = melody.bars

    def fit(bar, degree):
        tones = set(key.chord(degree).tones())
        score = 0.0
        for beat, p, d in melody.in_bar(bar):
            w = min(d, 2.0) * (1.6 if beat in (0, 2) else 1.0)
            score += w if p % 12 in tones else -0.7 * w
        return score

    # Viterbi over the bars
    best = [{}]
    for deg, common in cands:
        bonus = 2.0 if deg == home else 0.0
        best[0][deg] = (fit(0, deg) + 0.5 * common + bonus, [deg])
    for bar in range(1, bars):
        layer = {}
        for deg, common in cands:
            here = fit(bar, deg) + 0.5 * common
            prev = max(best[-1].items(), key=lambda kv: kv[1][0] + (0.8 if (kv[0], deg) in _MOVES else 0)
                       + (-0.3 if kv[0] == deg else 0))
            score = prev[1][0] + here + (0.8 if (prev[0], deg) in _MOVES else 0) + (-0.3 if prev[0] == deg else 0)
            layer[deg] = (score, prev[1][1] + [deg])
        best.append(layer)
    last = best[-1]
    ends_home = melody.notes and melody.notes[-1][1] % 12 == key.tonic
    if ends_home and bars > 1:           # it ends at home: so does the harmony
        return last[home][1]
    pick = max(last.items(), key=lambda kv: kv[1][0] + (0.8 if (kv[0], home) in _MOVES or bars == 1 else 0))
    return pick[1][1]


def lead_line(melody: Melody, bar: int, channel: int, vel: int = 96) -> list:
    """The melody's notes in bar `bar` as jam notes."""
    return [["note", b, channel, p, vel + (8 if b in (0, 2) else 0), d * 0.92] for b, p, d in melody.in_bar(bar)]

