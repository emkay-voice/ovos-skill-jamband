from ovos_skill_jamband.music import Key
from ovos_skill_jamband.words import Words

from conftest import ROOT


def words(lang):
    return Words(ROOT / "locale", lang)


def test_english():
    w = words("en-US")
    assert w.style("let's jam a blues in E") == "blues"
    assert w.key("let's jam a blues in E") == Key(4)
    assert w.key("play a funky one in a minor") == Key(9, True)
    assert w.key("play a blues") is None                 # "a" is not A
    assert w.key("in F sharp please") == Key(6)
    assert w.parts("give me drums and a bass") == ["drums", "bass"]
    assert w.has("no more piano", "remove") and w.parts("no more piano") == ["piano"]
    assert w.has("now the whole band", "everyone")
    assert w.tempo("tempo 128") == 128 and w.tempo("faster") is None
    assert w.spoken_key(Key(10, True)) == "B flat minor"


def test_danish():
    w = words("da-DK")
    assert w.key("lad os jamme en blues i d-dur") == Key(2)
    assert w.key("spil i fis mol") == Key(6, True)
    assert w.key("i b") == Key(10)                        # b is B flat, h is B
    assert w.parts("sæt bassen og trommerne ind") == ["bass", "drums"]
    assert w.has("hurtigere tak", "faster")
    assert w.spoken_key(Key(2, True)) == "d mol"


def test_german_and_romance():
    assert words("de-DE").key("ein Blues in Es") == Key(3)
    assert words("de-DE").key("spiel es nochmal") is None        # "es" is "it"
    assert words("es-ES").key("un blues en mi menor") == Key(4, True)
    assert words("es-ES").key("dame la batería") is None          # "la" is "the"
    assert words("fr-FR").key("en si bémol majeur") == Key(10)
    assert words("it-IT").parts("aggiungi la batteria e il basso") == ["drums", "bass"]


def test_every_language_knows_every_part_and_style():
    for d in (ROOT / "locale").iterdir():
        w = Words(ROOT / "locale", d.name)
        for name in ("drums", "bass", "piano", "guitar", "organ", "strings", "brass", "sax", "bandoneon",
                     "everyone", "remove", "faster", "slower", "finish", "major", "minor", "swing", "tango"):
            assert w.voc.get(name), (d.name, name)
