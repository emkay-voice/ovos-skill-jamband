"""What a sentence asks the band for: parts, a style, a key, a tempo.

The words are the locale's .voc files (drums.voc, swing.voc, faster.voc
...), so every language has its own. Keys are read from note names: letters
(D, F#, Bb; and German/Danish H, B, Fis, Es) or solfège (re, fa#, si
bemol), with major/minor ("D minor", "d-mol", "re menor"). A bare letter
counts as a key only after "in" (i, en, em ...) or before major/minor, so
"play a blues" is not in A.
"""
from __future__ import annotations

import re
from pathlib import Path

from .music import NAMES, Key
from .styles import PARTS, STYLES

LETTERS = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11, "h": 11}
SOLFEGE = {"do": 0, "re": 2, "ré": 2, "mi": 4, "fa": 5, "sol": 7, "la": 9, "si": 11}
#: German/Danish/Dutch: B is B flat, H is B; -is sharp, -es/-s flat
GERMANIC = {"b": 10, "h": 11, "cis": 1, "dis": 3, "fis": 6, "gis": 8, "ais": 10,
            "des": 1, "es": 3, "ges": 6, "as": 8, "bes": 10, "ces": 11}
SHARP = ("#", "♯", "sharp", "kryds", "sostenido", "dièse", "diese", "diesis", "sustenido", "sostingut", "kreuz")
FLAT = ("♭", "flat", "bemol", "bémol", "bemolle", "bemolle")
#: words before a key: "in D", "i d-mol", "en re menor"
KEY_PREPOSITIONS = {"in", "i", "en", "em"}
#: spoken note names, per language
SPOKEN = {
    "en": ["C", "C sharp", "D", "E flat", "E", "F", "F sharp", "G", "A flat", "A", "B flat", "B"],
    "da": ["c", "cis", "d", "es", "e", "f", "fis", "g", "as", "a", "b", "h"],
    "de": ["C", "Cis", "D", "Es", "E", "F", "Fis", "G", "As", "A", "B", "H"],
    "nl": ["C", "Cis", "D", "Es", "E", "F", "Fis", "G", "As", "A", "Bes", "B"],
    "es": ["do", "do sostenido", "re", "mi bemol", "mi", "fa", "fa sostenido", "sol", "la bemol", "la", "si bemol", "si"],
    "fr": ["do", "do dièse", "ré", "mi bémol", "mi", "fa", "fa dièse", "sol", "la bémol", "la", "si bémol", "si"],
    "it": ["do", "do diesis", "re", "mi bemolle", "mi", "fa", "fa diesis", "sol", "la bemolle", "la", "si bemolle", "si"],
    "pt": ["dó", "dó sustenido", "ré", "mi bemol", "mi", "fá", "fá sustenido", "sol", "lá bemol", "lá", "si bemol", "si"],
    "ca": ["do", "do sostingut", "re", "mi bemoll", "mi", "fa", "fa sostingut", "sol", "la bemoll", "la", "si bemoll", "si"],
    "gl": ["do", "do sostido", "re", "mi bemol", "mi", "fa", "fa sostido", "sol", "la bemol", "la", "si bemol", "si"],
    "eu": ["do", "do diesa", "re", "mi bemol", "mi", "fa", "fa diesa", "sol", "la bemol", "la", "si bemol", "si"],
}

#: how speech recognition writes a spoken letter name
SPELLED = {
    "en": {"see": "c", "sea": "c", "cee": "c", "dee": "d", "ee": "e", "eff": "f", "gee": "g", "jee": "g",
           "ay": "a", "bee": "b", "be": "b"},
    "da": {"se": "c", "ce": "c", "de": "d", "ef": "f", "ge": "g", "hå": "h", "be": "b"},
    "de": {"ce": "c", "de": "d", "ef": "f", "ge": "g", "ha": "h", "be": "b"},
    "nl": {"see": "c", "cee": "c", "dee": "d", "ef": "f", "gee": "g", "bee": "b"},
}


class Words:
    def __init__(self, locale_dir: Path, lang: str):
        self.lang = lang.split("-")[0].lower()
        self.voc = {}
        folder = self._folder(locale_dir, lang)
        for f in folder.glob("*.voc"):
            words = [w.strip().lower() for w in f.read_text(encoding="utf-8").splitlines()
                     if w.strip() and not w.startswith("#")]
            self.voc[f.stem] = sorted(words, key=len, reverse=True)

    @staticmethod
    def _folder(locale_dir: Path, lang: str) -> Path:
        want = lang.lower()
        for d in locale_dir.iterdir():
            if d.name.lower() == want:
                return d
        for d in locale_dir.iterdir():
            if d.name.lower().split("-")[0] == want.split("-")[0]:
                return d
        return locale_dir / "en-US"

    def has(self, utterance: str, name: str) -> bool:
        u = f" {normal(utterance)} "
        return any(f" {w} " in u for w in self.voc.get(name, []))

    def parts(self, utterance: str) -> list[str]:
        """The parts named, in the order they are said."""
        u = f" {normal(utterance)} "
        found = []
        for part in PARTS:
            for w in self.voc.get(part, []):
                i = u.find(f" {w} ")
                if i >= 0:
                    found.append((i, part))
                    break
        return [p for _, p in sorted(found)]

    def style(self, utterance: str) -> str | None:
        u = f" {normal(utterance)} "
        for name in STYLES:
            if any(f" {w} " in u for w in self.voc.get(name, [name])):
                return name
        return None

    def tempo(self, utterance: str) -> int | None:
        m = re.search(r"\b(\d{2,3})\b", utterance)
        return int(m.group(1)) if m and 40 <= int(m.group(1)) <= 240 else None

    def key(self, utterance: str) -> Key | None:
        tokens = normal(utterance).replace("-", " ").split()
        major, minor = self.voc.get("major", []), self.voc.get("minor", [])
        for i, tok in enumerate(tokens):
            rest = " ".join(tokens[i + 1:i + 3])
            pc, used = note(tok, rest, self.lang)
            if pc is None:
                continue
            after = tokens[i + 1 + used:i + 2 + used]
            is_minor = bool(after and after[0] in minor)
            is_major = bool(after and after[0] in major)
            before = tokens[i - 1] if i else ""
            # a note name is also an everyday word ("a", "la", "mi", "es"):
            # only after "in", or with major/minor or a sharp/flat sign
            if before in KEY_PREPOSITIONS or is_minor or is_major or any(c in tok for c in "#♯♭"):
                return Key(pc, is_minor)
        return None

    def notes(self, utterance: str, strict: bool = True):
        """A melody said as note names ("C D E C", "do re mi do"), or None.
        `strict`: most of the words must be notes (else a sentence like "a
        bass in E" would be a tune)."""
        from .melody import from_names
        tokens = normal(utterance).replace("-", " ").split()
        lang = self.lang
        spelled = SPELLED.get(lang, {})
        tokens = [spelled.get(t, t) for t in tokens]
        rest = set(self.voc.get("rest", []))
        found = [t for i, t in enumerate(tokens) if note(t, "", lang)[0] is not None or t in rest]
        if len(found) < 3 or (strict and len(found) < 0.6 * len(tokens)):
            return None
        return from_names(tokens, lambda t, after: note(t, after, lang), rest)

    def bare_key(self, utterance: str) -> Key | None:
        """The answer to "which key?": a note name alone will do ("E", "fis mol")."""
        tokens = normal(utterance).replace("-", " ").split()
        if not tokens or len(tokens) > 4:
            return None
        minor = self.voc.get("minor", [])
        for i, tok in enumerate(tokens):
            pc, used = note(tok, " ".join(tokens[i + 1:i + 3]), self.lang)
            if pc is not None:
                after = tokens[i + 1 + used:i + 2 + used]
                return Key(pc, bool(after and after[0] in minor))
        return None

    def spoken_key(self, key: Key) -> str:
        names = SPOKEN.get(self.lang, SPOKEN["en"])
        word = (self.voc.get("minor") if key.minor else self.voc.get("major")) or ["minor" if key.minor else "major"]
        return f"{names[key.tonic]} {word[-1]}"


def normal(text: str) -> str:
    return re.sub(r"[^\w#♯♭'-]+", " ", text.lower()).strip()


def note(tok: str, rest: str, lang: str):
    """(pitch class, how many following words it used) for a note name, else (None, 0)."""
    germanic = lang in ("da", "de", "nl")
    t = tok.rstrip(".,!?")
    pc = None
    if germanic and t in GERMANIC:
        pc = GERMANIC[t]
    elif t in SOLFEGE:
        pc = SOLFEGE[t]
    elif t[:1] in LETTERS and (len(t) == 1 or t[1:] in ("#", "♯", "b", "♭")):
        if germanic and t == "b":
            pc = 10
        else:
            pc = LETTERS[t[0]] + (1 if t[1:] in ("#", "♯") else -1 if t[1:] in ("b", "♭") else 0)
    if pc is None:
        return None, 0
    words = rest.split()
    if words and words[0] in SHARP:
        return (pc + 1) % 12, 1
    if words and words[0] in FLAT:
        return (pc - 1) % 12, 1
    return pc % 12, 0


def key_name(key: Key) -> str:
    return NAMES[key.tonic] + ("m" if key.minor else "")
