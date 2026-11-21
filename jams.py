"""Saved jams: a JSON file each (how it began and what happened when), and
a Standard MIDI File next to it, to take to any other program.

    jams = Jams(folder)
    jams.save("Friday blues", jam.recording(), lang="en-US")
    jams.find("friday blues")      -> the saved jam, by name, roughly
    jams.names()                   -> what there is, newest first
"""
from __future__ import annotations

import difflib
import json
import re
import struct
import time
import unicodedata
from pathlib import Path

from .jam import render

PPQ = 480


def slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "jam"


class Jams:
    """Your jams in `folder`; the ones that come with the skill in `bundled`
    (they can't be deleted, and have a name in every language: "names")."""

    def __init__(self, folder: Path, bundled: Path | None = None):
        self.folder = Path(folder)
        self.bundled = Path(bundled) if bundled else None

    def _path(self, name: str) -> Path:
        return self.folder / f"{slug(name)}.json"

    def save(self, name: str, recording: dict, **extra) -> Path:
        self.folder.mkdir(parents=True, exist_ok=True)
        data = {"name": name.strip(), "saved": time.time(), **extra, **recording}
        path = self._path(name)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        try:
            write_midi(path.with_suffix(".mid"), data)
        except Exception:      # the jam is saved; the MIDI file is a bonus
            pass
        return path

    def all(self) -> list[dict]:
        """Yours, newest first, then the ones that come with the skill."""
        def read(folder, bundled):
            out = []
            for p in sorted(folder.glob("*.json")) if folder and folder.is_dir() else []:
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if bundled:
                    d["bundled"] = True
                out.append(d)
            return out
        mine = sorted(read(self.folder, False), key=lambda d: -d.get("saved", 0))
        return mine + read(self.bundled, True)

    @staticmethod
    def _slugs(d: dict) -> list[str]:
        return [slug(d.get("name", ""))] + [slug(n) for n in (d.get("names") or {}).values()]

    def names(self) -> list[str]:
        return [d["name"] for d in self.all()]

    def find(self, name: str) -> dict | None:
        """The saved jam called `name`, or the one whose name is closest."""
        jams = self.all()
        if not jams or not name:
            return jams[0] if jams and not name else None
        want = slug(name)
        for d in jams:
            if want in self._slugs(d):
                return d
        for d in jams:                                   # "play friday" for "Friday blues"
            if any(want in s or s in want for s in self._slugs(d) if s):
                return d
        every = [(s, d) for d in jams for s in self._slugs(d)]
        close = difflib.get_close_matches(want, [s for s, _ in every], n=1, cutoff=0.6)
        return next((d for s, d in every if s == close[0]), None) if close else None

    def latest(self) -> dict | None:
        jams = [d for d in self.all() if not d.get("bundled")] or self.all()
        return jams[0] if jams else None

    def delete(self, name: str) -> str | None:
        d = self.find(name)
        if not d or d.get("bundled"):
            return None
        path = self._path(d["name"])
        for p in (path, path.with_suffix(".mid")):
            if p.exists():
                p.unlink()
        return d["name"]


# ------------------------------------------------------------------ MIDI file
def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append(0x80 | (n & 0x7F))
        n >>= 7
    return bytes(reversed(out))


def midi_bytes(recording: dict, title: str = "") -> bytes:
    """A type 0 Standard MIDI File of a saved jam: a bar is four beats at
    the tempo it had, so the file plays as the jam did."""
    timed = []                                   # (tick, order, bytes)
    tempo = None
    tick0 = 0
    for bar, bpm, events in render(recording):
        beat = 60.0 / bpm
        if bpm != tempo:
            us = int(60_000_000 / bpm)
            timed.append((tick0, 0, b"\xff\x51\x03" + us.to_bytes(3, "big")))
            tempo = bpm
        for e in events:
            kind = e[0]
            at = tick0 + int(round(e[1] / beat * PPQ))
            if kind == "note":
                _, _, ch, pitch, vel, dur = e
                off = tick0 + int(round((e[1] + dur) / beat * PPQ))
                timed.append((at, 2, bytes([0x90 | ch, pitch, vel])))
                timed.append((max(off, at + 1), 1, bytes([0x80 | ch, pitch, 0])))
            elif kind == "program":
                timed.append((at, 0, bytes([0xC0 | e[2], e[3] & 0x7F])))
            elif kind == "cc":
                timed.append((at, 0, bytes([0xB0 | e[2], e[3] & 0x7F, e[4] & 0x7F])))
        tick0 += 4 * PPQ
    timed.sort(key=lambda x: (x[0], x[1]))
    track = bytearray()
    if title:
        t = title.encode("utf-8")[:120]
        track += _vlq(0) + b"\xff\x03" + _vlq(len(t)) + t
    track += _vlq(0) + b"\xff\x58\x04\x04\x02\x18\x08"           # 4/4
    last = 0
    for tick, _, data in timed:
        track += _vlq(tick - last) + data
        last = tick
    track += _vlq(PPQ) + b"\xff\x2f\x00"
    head = b"MThd" + struct.pack(">IHHH", 6, 0, 1, PPQ)
    return head + b"MTrk" + struct.pack(">I", len(track)) + bytes(track)


def write_midi(path: Path, recording: dict):
    Path(path).write_bytes(midi_bytes(recording, recording.get("name", "")))
