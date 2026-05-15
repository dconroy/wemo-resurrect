from __future__ import annotations

import logging
import os
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from .. import database as db
from ..config import get_settings
from ..deps import get_db, require_admin
from ..schemas import DiscoverOut, device_from_row
from ..wemo_client import WemoClientError, discover_wemos

LOG = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["discover"])

_DOCKER_HINT = (
    "No WeMo devices replied to SSDP from this process. "
    "SSDP multicast often fails inside Docker’s default bridge network—try "
    "“Add by IP”, run the stack on Linux with host networking (see README), "
    "or run uvicorn on the host instead of a container."
)


@router.post("/discover", response_model=DiscoverOut, dependencies=[Depends(require_admin)])
def run_discovery(conn: sqlite3.Connection = Depends(get_db)) -> DiscoverOut:
    timeout = float(get_settings().discovery_ssdp_timeout)
    try:
        found = discover_wemos(debug=False, ssdp_timeout=timeout)
    except WemoClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    for snap in found:
        db.upsert_device(
            conn,
            name=snap.name,
            ip=snap.ip,
            port=snap.port,
            model=snap.model,
            serial=snap.serial,
            udn=snap.udn,
        )
        cur = conn.execute("SELECT id FROM devices WHERE udn = ?", (snap.udn,))
        did = int(cur.fetchone()[0])
        if snap.binary_state is not None:
            db.update_device_status(
                conn, did, online=True, last_state=snap.binary_state, last_error=None
            )
        else:
            db.update_device_status(conn, did, online=False, last_state=None, last_error=None)

    devices = [device_from_row(r) for r in db.list_devices(conn)]
    n = len(found)
    msg: str | None = None
    if n == 0:
        in_container = os.path.isfile("/.dockerenv")
        msg = _DOCKER_HINT if in_container else (
            "No WeMo devices replied to SSDP. Check that you are on the same LAN as the plugs, "
            "that UDP multicast is allowed, or use “Add by IP”."
        )
    LOG.info("Discovery finished: %s device(s) this run, %s total in database", n, len(devices))
    return DiscoverOut(devices=devices, discovered_this_run=n, message=msg)
