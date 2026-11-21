from ovos_skill_jamband import melody as M
from ovos_skill_jamband.music import Key
from ovos_skill_jamband.words import Words

from conftest import ROOT, hum


def test_humming_is_heard_in_tune_and_in_time():
    tune = [60, 62, 64, 60, 64, 65, 67, 67]
    x, sr = hum(tune)
    mel, tempo, key = M.from_audio(x, sr)
    assert abs(tempo - 100) <= 4 and key == Key(0)
    assert [p % 12 for p in mel.pitches()] == [p % 12 for p in tune]
    assert [b for b, _, _ in mel.notes] == list(range(8)) and mel.bars == 2


def test_humming_at_the_jams_tempo():
    x, sr = hum([57, 60, 64, 62], tempo=120)
    mel, tempo, _ = M.from_audio(x, sr, tempo=120)
    assert tempo == 120 and [b for b, _, _ in mel.notes] == [0, 1, 2, 3]


def test_said_notes_in_three_languages():
    en = Words(ROOT / "locale", "en-US")
    assert en.notes("C D E C").pitches() == [60, 62, 64, 60]
    assert en.notes("the notes are E G A, E G B flat A").pitches() == [64, 67, 69, 64, 67, 70, 69]
    assert en.notes("add a bass in E") is None                  # a sentence, not a tune
    da = Words(ROOT / "locale", "da-DK")
    assert da.notes("c d e f g pause g").pitches() == [60, 62, 64, 65, 67, 67]
    fr = Words(ROOT / "locale", "fr-FR")
    assert [p % 12 for p in fr.notes("do ré mi do").pitches()] == [0, 2, 4, 0]


def test_played_on_a_keyboard():
    t0, beat = 1000.0, 0.5               # 120 bpm
    ev = []
    for k, n in enumerate([60, 64, 67, 72]):
        ev += [(t0 + k * beat + 0.02, "on", n), (t0 + (k + 0.9) * beat, "off", n)]
    ev += [(t0 + 2 * beat, "on", 48), (t0 + 2.5 * beat, "off", 48)]     # a chord: the top note is the tune
    mel = M.from_played(ev, 120)
    assert mel.pitches() == [60, 64, 67, 72] and [b for b, _, _ in mel.notes] == [0, 1, 2, 3]


def test_chords_that_fit_and_come_home():
    mel = M.Melody.of([(0, 60, 1), (1, 64, 1), (2, 67, 2), (4, 65, 1), (5, 62, 1), (6, 67, 2),
                       (8, 64, 2), (10, 60, 2), (12, 62, 1), (13, 67, 1), (14, 60, 2)])
    chords = M.fit_chords(mel, Key(0))
    assert chords[0] == "I" and chords[-1] == "I" and chords[1] in ("V7", "ii7")
    assert M.key_of(mel.notes) == Key(0)
