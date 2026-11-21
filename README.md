# <img src='icon.png' card_color='#ffcc33' width='50' height='50' style='vertical-align:bottom'/> Jam Band

A band you lead with your voice. Ask for drums, and the drums start. Ask for
a bass, and it comes in on the next bar. Ask for the whole band, and you get
the whole orchestra. Emkay comments as it goes, then listens again.

```
"let's jam"                     "Let's jam! A swing in F major. What do we start with? Drums?"
"drums"                         the drums start - "Yeah! That's good."
"and now a bass"                "Ohhh, listen to that bass!"
"the whole band"                "And now... the whole orchestra!"
"faster" / "slower" / "tempo 120"
"make it reggae" / "in G minor"
"no more piano"
"let's finish"                  one big last chord - "Thank you, thank you!"
"stop"                          stops at once

"lad os jamme en blues i e"     (Danish)
"sæt bassen ind", "hele bandet", "hurtigere", "lad os slutte"
```

You can also say it all at once: "jam a funk in E minor with drums and
bass", or "jam a blues at 100".

It speaks every language Emkay does: English, Danish, German, Spanish,
French, Italian, Dutch, Portuguese (Portugal and Brazil), Catalan, Basque and
Galician. It understands keys as letters (D, F sharp, B flat; and Danish and
German H, B, Fis, Es) or as solfège (re, si bemol), with major and minor.

[![Build](https://github.com/emkay-voice/ovos-skill-jamband/actions/workflows/publish.yml/badge.svg)](https://github.com/emkay-voice/ovos-skill-jamband/actions/workflows/publish.yml)
[![PyPI version](https://img.shields.io/pypi/v/ovos-skill-jamband.svg)](https://pypi.org/project/ovos-skill-jamband/)

## The styles

| Style | The groove | Key, tempo |
|---|---|---|
| swing | ride cymbal, walking bass, Charleston piano, sax and brass punches | F, 140 |
| blues | 12-bar shuffle, boogie bass, organ | E, 92 |
| rock | eighth-note bass, power chords | A, 120 |
| pop | I-V-vi-IV, piano on every beat | C, 104 |
| funk | sixteenths, slap bass, muted guitar scratch, horn stabs | E minor, 104 |
| disco | four on the floor, octave bass, strings | A minor, 120 |
| reggae | one drop, the skank on 2 and 4, organ bubble | G, 76 |
| bossa | rim-click pattern, nylon guitar, Rhodes | C, 128 |
| tango | the bandoneon marking every beat, then the 3-3-2, the bass dragging into 3 | D minor, 112 |

Every part has its own groove in every style: drums, bass, piano, guitar,
organ, strings, brass, sax and bandoneon. "The whole band" brings in the
style's own band, part by part. A key you ask for stays when you change the
style. The style's default key changes it only if you never chose one.

The screen shows the chord now, big, the next ones, and who is playing.

## The band behind it

The music is played by [ovos-phal-plugin-midi](https://github.com/emkay-voice/ovos-phal-plugin-midi),
the device's MIDI instrument. It is installed with the skill and runs in
OVOS' PHAL service, so restart OpenVoiceOS once after installing. Emkay
starts it by itself. Until it runs, the skill says its band isn't ready.

The jam sends the plugin the next bar while this one plays. When you change
something, the bar already sent is taken back (`ovos.midi.cancel`) and sent
again, changed. That is why a change is heard on the next bar line and the
music never stops. While OVOS speaks or listens, the plugin turns the music
down.

How it sounds is up to the plugin. Its own synth needs nothing. With
FluidSynth and a SoundFont it plays real instrument samples. It can also play
a real instrument plugged into the device. See its README.

While the jam plays, what you say goes to it first (OVOS' converse). After
Emkay answers, it listens again, so you can keep leading the band without
the wake word. Anything that isn't for the band ("what's the weather?") is
left for the rest of OVOS.

## Install
```bash
pip install --pre ovos-skill-jamband
```

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md).

## Category
**Entertainment**

## Tags
#music #jam #band #midi #fun
