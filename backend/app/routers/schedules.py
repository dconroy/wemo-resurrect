from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from .. import database as db
from ..deps import get_db, require_admin
from ..schemas import ScheduleCreate, ScheduleOut, ScheduleUpdate
from ..scheduler_service import notify_schedule_changed

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


@router.get("", response_model=list[ScheduleOut], dependencies=[Depends(require_admin)])
def list_schedules(
    device_id: int | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[ScheduleOut]:
    return [ScheduleOut.from_row(r) for r in db.list_schedules(conn, device_id)]


@router.post("", response_model=ScheduleOut, dependencies=[Depends(require_admin)])
def create_schedule(body: ScheduleCreate, conn: sqlite3.Connection = Depends(get_db)) -> ScheduleOut:
    if not db.get_device(conn, body.device_id):
        raise HTTPException(status_code=404, detail="Device not found")
    row = db.create_schedule(
        conn,
        device_id=body.device_id,
        action=body.action,
        time_of_day=body.time_of_day,
        days_of_week=body.days_of_week,
        enabled=body.enabled,
    )
    notify_schedule_changed()
    return ScheduleOut.from_row(row)


@router.put("/{schedule_id}", response_model=ScheduleOut, dependencies=[Depends(require_admin)])
def update_schedule(
    schedule_id: int,
    body: ScheduleUpdate,
    conn: sqlite3.Connection = Depends(get_db),
) -> ScheduleOut:
    if body.device_id is not None and not db.get_device(conn, body.device_id):
        raise HTTPException(status_code=404, detail="Device not found")
    row = db.update_schedule(
        conn,
        schedule_id,
        device_id=body.device_id,
        action=body.action,
        time_of_day=body.time_of_day,
        days_of_week=body.days_of_week,
        enabled=body.enabled,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")
    notify_schedule_changed()
    return ScheduleOut.from_row(row)


@router.delete("/{schedule_id}", dependencies=[Depends(require_admin)])
def delete_schedule(schedule_id: int, conn: sqlite3.Connection = Depends(get_db)) -> dict[str, bool]:
    ok = db.delete_schedule(conn, schedule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Schedule not found")
    notify_schedule_changed()
    return {"ok": True}
