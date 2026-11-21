# Developing ovos-skill-jamband

```bash
pip install -e ".[test]"
pytest -q tests
```

(`tests/pytest.ini` keeps pytest from importing the repository root's
`__init__.py` as a plain module; the tests use the installed package.)

## The pieces

| file | |
|---|---|
| `music.py` | keys, chords, degrees (I, IV7, vi ...) and voicings that move smoothly |
| `styles.py` | the styles: for every part, what it plays in a bar |
| `jam.py` | the jam's state, sent a bar ahead to ovos-phal-plugin-midi; a change cancels and resends |
| `words.py` | what a sentence asks for: parts, style, key, tempo (the locale's `.voc` files) |
| `screen.py` | the chord now, the next ones and the band, as an SVG for `SYSTEM_ImageFrame` |
| `__init__.py` | the skill: "let's jam", then converse while it plays |

Everything is pure Python, so it also runs in Pyodide (Emkay).

## The bus

The jam speaks to [ovos-phal-plugin-midi](https://github.com/emkay-voice/ovos-phal-plugin-midi):

- `ovos.midi.status` once, for its latency.
- `ovos.midi.events` every bar, one bar ahead, with the skill id as `source`
  and the bar's start as `at`.
- `ovos.midi.cancel` with `after` when something changes: the bar already
  sent is taken back and sent again.
- `ovos.midi.stop` at the end.

## A new style

Add a `Style` to `STYLES` in `styles.py`: its tempo, key, progression (as
degrees), the GM programs, the parts of "the whole band", the drum pattern,
the bass kind and the comping rhythms. Then add its words: a `<style>.voc`
in every locale. `tests/test_jam.py` checks that every part of every style
plays.

## Languages

Every locale has the same files (`tests/test_skill.py` checks): `jam.intent`,
a `.voc` per part, style and command, and the dialogs, with a comment for
each part as it comes in (`in_drums.dialog` ...) and its name (`name_drums.dialog`).
Corrections from native speakers are very welcome.
