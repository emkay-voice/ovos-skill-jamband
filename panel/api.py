"""The Jamband page's API: thin relays to the skill over the message bus."""
import base64
import re
from urllib.parse import quote
from typing import Any

from fastapi import HTTPException, Response
from pydantic import BaseModel, Field

LIST = "ovos.jamband.jams.list"
RENAME = "ovos.jamband.jams.rename"
DELETE = "ovos.jamband.jams.delete"
MIDI = "ovos.jamband.jams.midi"
PLAY = "ovos.jamband.jams.play"
STOP = "ovos.jamband.stop"
TIMEOUT = 10.0
#: what a jam's id looks like: a file name, "skill:" for the skill's own
JAM_ID = r"^(skill:)?[a-z0-9-]{1,120}$"


class IdBody(BaseModel):
    id: str = Field(pattern=JAM_ID)


class RenameBody(IdBody):
    name: str = Field(min_length=1, max_length=120)


def ask(r, msg_type: str, data: dict | None = None) -> dict[str, Any]:
    """Send a message to the skill and give back its answer."""
    from ovos_bus_client.message import Message
    bus = r.need_bus()
    message = Message(msg_type, data or {})
    try:
        from ovos_webui import buswait
        reply = buswait.wait_for_response(bus, message, timeout=TIMEOUT)
    except ImportError:  # an older panel: the bus client's own wait
        reply = bus.wait_for_response(message, timeout=TIMEOUT)
    if reply is None:
        raise HTTPException(504, "the jam band skill did not answer; is it running?")
    if reply.data.get("error"):
        raise HTTPException(400, reply.data["error"])
    return reply.data


def routes(r):
    @r.api.get("/jamband/jams")
    def jams() -> dict[str, Any]:
        return ask(r, LIST)

    @r.api.post("/jamband/rename")
    def rename(body: RenameBody) -> dict[str, Any]:
        return ask(r, RENAME, {"id": body.id, "name": body.name.strip()})

    @r.privileged.post("/jamband/delete")
    def delete(body: IdBody) -> dict[str, Any]:
        return ask(r, DELETE, {"id": body.id})

    @r.api.post("/jamband/play")
    def play(body: IdBody) -> dict[str, Any]:
        return ask(r, PLAY, {"id": body.id})

    @r.api.post("/jamband/stop")
    def stop() -> dict[str, Any]:
        return ask(r, STOP)

    @r.api.get("/jamband/midi")
    def midi(id: str) -> Response:
        if not re.match(JAM_ID, id or ""):
            raise HTTPException(400, "that is not a jam")
        found = ask(r, MIDI, {"id": id})
        try:
            data = base64.b64decode(found.get("midi") or "", validate=True)
        except ValueError as err:
            raise HTTPException(502, "the skill sent no MIDI file") from err
        title = (found.get("name") or "jam").strip()[:120] or "jam"
        plain = re.sub(r"[^A-Za-z0-9._ -]+", "", title).strip() or "jam"
        return Response(data, media_type="audio/midi", headers={
            # the plain name for old browsers, the real one (Fredagsblåt) for the rest
            "Content-Disposition": f'attachment; filename="{plain}.mid"; '
                                   f"filename*=UTF-8''{quote(title)}.mid",
            "X-Content-Type-Options": "nosniff"})
