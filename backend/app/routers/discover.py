from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from .. import database as db
from ..deps import get_db, require_admin
from ..schemas import DeviceOut, device_from_row
from ..wemo_client import WemoClientError, discover_wemos

router = APIRouter(prefix="/api", tags=["discover"])


@router.post("/discover", response_model=list[DeviceOut], dependencies=[Depends(require_admin)])
def run_discovery(conn: sqlite3.Connection = Depends(get_db)) -> list[DeviceOut]:
    try:
        found = discover_wemos(debug=False)
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
    return [device_from_row(r) for r in db.list_devices(conn)]
