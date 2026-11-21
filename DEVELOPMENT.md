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
| `styles.py` | what every part plays in a bar; loads the styles from `styles/*.json` |
| `solo.py` | an improvised solo, a bar at a time, from the style's scale and the chord |
| `melody.py` | a melody: from note names, a MIDI keyboard or humming (YIN pitch tracking); its key; chords that fit it |
| `listen.py` | the microphone (the listener's recording mode) and the keyboard (`ovos.midi.input`) |
| `tunes.py` | the library, `tunes/*.json`, and ovos-skill-karaoke's songbook when it is installed |
| `compose.py` | Emkay's own jam: a whole arrangement, written as a saved jam's log |
| `jam.py` | the jam's state, sent a bar ahead to ovos-phal-plugin-midi; a change cancels and resends; moments (intro, solo, break, top, ending); the log of everything that happens, and playing a log back |
| `jams.py` | saved jams (JSON, and a MIDI file each); the ones in `jams/` come with the skill |
| `words.py` | what a sentence asks for: parts, style, key, tempo, note names (the locale's `.voc` files) |
| `screen.py` | the chord now, the next ones and the band, as an SVG for `SYSTEM_ImageFrame` |
| `__init__.py` | the skill: the intents, then converse while it plays (and for Emkay's questions) |

Everything is pure Python, so it also runs in Pyodide (Emkay).

## The bus

The jam speaks to [ovos-phal-plugin-midi](https://github.com/emkay-voice/ovos-phal-plugin-midi):

- `ovos.midi.status` once, for its latency.
- `ovos.midi.events` every bar, one bar ahead, with the skill id as `source`
  and the bar's start as `at`.
- `ovos.midi.cancel` with `after` when something changes: the bar already
  sent is taken back and sent again.
- `ovos.midi.stop` at the end (and to hold still while it hears your melody).
- `ovos.midi.input` from the plugin: keys pressed on a MIDI keyboard.

And to the listener: `recognizer_loop:state.set` `{"state": "recording",
"recording_name": ...}`, then `recognizer_loop:record_stop` if it runs long;
when `recognizer_loop:record_end` comes, the WAV is in the listener's
`<save_path>/recordings/`.

## A saved jam

```json
{"name": "Friday blues", "saved": 1763712000.0, "lang": "en-US",
 "first": {"style": "blues", "key": [4, false], "tempo": 92, "parts": [], "melody": null, ...},
 "log": [{"bar": 0, "do": "change", "args": {"parts": ["drums"]}},
         {"bar": 4, "do": "solo", "args": {"part": "sax", "bars": 12}},
         {"bar": 16, "do": "break", "args": {}},
         {"bar": 24, "do": "finish", "args": {}}],
 "bars": 25}
```

`first` is how the jam began, `log` what happened at which bar: `change`
(style, key, tempo, parts, chords, melody, lead), `solo`, `break`, `top`,
`intro`, `finish`, and `end` when it was stopped. Playing it back does the
same things at the same bars; the solos are drawn from the state's `seed`,
so they come out the same. The ones in `jams/` have `names`, one per
language.

## A new style

A new file in `styles/`, named after the style: its tempo, key, progression
(as degrees), "the whole band" in the order it comes in, General MIDI
programs, the drum pattern (`["ride", beat, velocity]`), the bass kind (one of
`styles.BASSES`) and the comping rhythm of each part (`[beat, beats]`). Then
its words: a `<style>.voc` in every locale. `tests/test_library.py` checks
every style file, `tests/test_jam.py` that every part plays.

## A new tune

A new file in `tunes/`: its names (as many languages as you know - any of
them finds it), its key, optionally `say` (the name to say, per language)
and `chords` (degrees, a bar each, where the usual chords differ from what
`melody.fit_chords` picks), and the notes, a bar per line:

```json
{
 "names": ["Frère Jacques", "Brother John", "Mester Jakob", "Bruder Jakob"],
 "key": "C",
 "notes": [
  "C4 D4 E4 C4",
  "G4:.5 A4:.5 G4:.5 F4:.5 E4 C4",
  "C4 G3 C4:2"
 ]
}
```

A note is `NOTE[:beats]` (`E4` a beat, `D#5:.5` an eighth, `r:2` two beats'
rest); bars are four beats (the tests check). Only tunes free to use:
traditional, or by composers who died more than 70 years ago - a melody is
protected just like words.

## Languages

Every locale has the same files (`tests/test_skill.py` checks): `jam.intent`,
a `.voc` per part, style and command, and the dialogs, with a comment for
each part as it comes in (`in_drums.dialog` ...) and its name (`name_drums.dialog`).
Corrections from native speakers are very welcome.
