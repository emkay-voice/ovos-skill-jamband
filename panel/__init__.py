"""The Jamband page in ovos-control-panel.

The control panel finds this page through the ``opm.control_panel.page``
entry point (see pyproject.toml and the panel's docs/pages.md). It lists the
saved jams, yours and the ones that come with the skill: play one, give it
another name, download it as a MIDI file, or delete it. Nothing here is
loaded by the skill itself, so the skill needs no web packages; the panel
brings those.
"""


def routes(r):
    # Imported here, so reading PAGE (the panel's registry, this skill's
    # tests) needs no web framework; only the panel calls this.
    from ovos_skill_jamband.panel.api import routes as add
    add(r)


#: the panel's Music group: music you make with the device. Newer panels have
#: it themselves; this brings it to older ones, and its name to the
#: languages the panel itself has no strings for
MUSIC = {"id": "music", "title": {"key": "nav.group.music", "label": "Music"},
         "order": 6, "level": "everyday"}

PAGE = {
    "api_version": 1,
    "id": "jamband",
    "path": "/jamband",
    "title": {"key": "jamband.title", "label": "Jam band"},
    "group": "music",
    "groups": [MUSIC],
    "order": 10,
    "needs": ["ovos-skill-jamband"],
    "html": "page.html",
    "icon": "icon.svg",
    "i18n": "i18n",
    "routes": routes,
}
