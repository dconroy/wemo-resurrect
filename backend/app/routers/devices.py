from __future__ import annotations

import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from .. import database as db
from ..deps import get_db, require_admin
from ..schemas import DeviceOut, ManualDeviceIn, StatusOut, device_from_row
from ..wemo_client import WemoClientError, get_device_snapshot, set_device_power

LOG = logging.getLogger(__name__)

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("", response_model=list[DeviceOut], dependencies=[Depends(require_admin)])
def list_devices(conn: sqlite3.Connection = Depends(get_db)) -> list[DeviceOut]:
    return [device_from_row(r) for r in db.list_devices(conn)]


@router.post("/manual", response_model=DeviceOut, dependencies=[Depends(require_admin)])
def add_manual(body: ManualDeviceIn, conn: sqlite3.Connection = Depends(get_db)) -> DeviceOut:
    try:
        snap = get_device_snapshot(body.ip.strip())
    except WemoClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    name = body.name.strip() if body.name else snap.name
    row = db.upsert_device(
        conn,
        name=name,
        ip=snap.ip,
        port=snap.port,
        model=snap.model,
        serial=snap.serial,
        udn=snap.udn,
    )
    did = int(row["id"])
    try:
        db.update_device_status(
            conn,
            did,
            online=True,
            last_state=snap.binary_state,
            last_error=None,
        )
    except Exception:
        LOG.exception("Could not persist status for new device %s", did)
    refreshed = db.get_device(conn, did)
    assert refreshed is not None
    return device_from_row(refreshed)


@router.get("/{device_id}/status", response_model=StatusOut, dependencies=[Depends(require_admin)])
def device_status(device_id: int, conn: sqlite3.Connection = Depends(get_db)) -> StatusOut:
    row = db.get_device(conn, device_id)
    if not row:
        raise HTTPException(status_code=404, detail="Device not found")
    ip = str(row["ip"])
    try:
        snap = get_device_snapshot(ip)
        db.update_device_status(
            conn,
            device_id,
            online=True,
            last_state=snap.binary_state,
            last_error=None,
        )
        refreshed = db.get_device(conn, device_id)
        assert refreshed is not None
        return StatusOut(
            device_id=device_id,
            online=True,
            last_state=refreshed["last_state"],
            last_state_at=refreshed["last_state_at"],
            last_error=refreshed["last_error"],
        )
    except WemoClientError as exc:
        db.update_device_status(
            conn, device_id, online=False, last_state=None, last_error=str(exc)
        )
        return StatusOut(
            device_id=device_id,
            online=False,
            last_state=row["last_state"],
            last_state_at=row["last_state_at"],
            last_error=str(exc),
        )


@router.post("/{device_id}/on", response_model=StatusOut, dependencies=[Depends(require_admin)])
def device_on(device_id: int, conn: sqlite3.Connection = Depends(get_db)) -> StatusOut:
    row = db.get_device(conn, device_id)
    if not row:
        raise HTTPException(status_code=404, detail="Device not found")
    ip = str(row["ip"])
    try:
        snap = set_device_power(ip, True)
        db.update_device_status(
            conn,
            device_id,
            online=True,
            last_state=snap.binary_state,
            last_error=None,
        )
        refreshed = db.get_device(conn, device_id)
        assert refreshed is not None
        return StatusOut(
            device_id=device_id,
            online=True,
            last_state=refreshed["last_state"],
            last_state_at=refreshed["last_state_at"],
            last_error=None,
        )
    except WemoClientError as exc:
        db.update_device_status(
            conn, device_id, online=False, last_state=None, last_error=str(exc)
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{device_id}/off", response_model=StatusOut, dependencies=[Depends(require_admin)])
def device_off(device_id: int, conn: sqlite3.Connection = Depends(get_db)) -> StatusOut:
    row = db.get_device(conn, device_id)
    if not row:
        raise HTTPException(status_code=404, detail="Device not found")
    ip = str(row["ip"])
    try:
        snap = set_device_power(ip, False)
        db.update_device_status(
            conn,
            device_id,
            online=True,
            last_state=snap.binary_state,
            last_error=None,
        )
        refreshed = db.get_device(conn, device_id)
        assert refreshed is not None
        return StatusOut(
            device_id=device_id,
            online=True,
            last_state=refreshed["last_state"],
            last_state_at=refreshed["last_state_at"],
            last_error=None,
        )
    except WemoClientError as exc:
        db.update_device_status(
            conn, device_id, online=False, last_state=None, last_error=str(exc)
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc
