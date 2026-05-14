"""APScheduler integration: load persisted schedules and fire local WeMo actions."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from . import database as db
from .wemo_client import WemoClientError, set_device_power

if TYPE_CHECKING:
    from apscheduler.schedulers.base import BaseScheduler

LOG = logging.getLogger(__name__)

_DOW_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

_scheduler: BackgroundScheduler | None = None


def _job_id(schedule_id: int) -> str:
    return f"wemo_schedule_{schedule_id}"


def _run_schedule(device_id: int, action: str, schedule_id: int) -> None:
    LOG.info("Running schedule %s device=%s action=%s", schedule_id, device_id, action)
    try:
        with db.db_conn() as conn:
            row = db.get_device(conn, device_id)
            if not row:
                LOG.error("Schedule %s: device %s missing", schedule_id, device_id)
                return
            ip = str(row["ip"])
        on = action == "on"
        snap = set_device_power(ip, on)
        with db.db_conn() as conn:
            db.update_device_status(
                conn,
                device_id,
                online=True,
                last_state=snap.binary_state,
                last_error=None,
            )
    except WemoClientError as exc:
        LOG.warning("Schedule %s failed: %s", schedule_id, exc)
        try:
            with db.db_conn() as conn:
                db.update_device_status(
                    conn, device_id, online=False, last_state=None, last_error=str(exc)
                )
        except Exception:
            LOG.exception("Could not persist offline state for device %s", device_id)
    except Exception:
        LOG.exception("Schedule %s failed", schedule_id)


def _days_to_trigger(days: list[int]) -> str:
    return ",".join(_DOW_NAMES[d] for d in sorted(set(days)))


def sync_scheduler_jobs(sched: BaseScheduler | None = None) -> None:
    target = sched or _scheduler
    if target is None:
        return
    for job in list(target.get_jobs()):
        if job.id.startswith("wemo_schedule_"):
            target.remove_job(job.id)
    with db.db_conn() as conn:
        rows = db.list_schedules(conn)
    for row in rows:
        if not row["enabled"]:
            continue
        try:
            days = db.parse_days_json(row["days_of_week"])
        except (ValueError, TypeError) as exc:
            LOG.warning("Bad days_of_week for schedule %s: %s", row["id"], exc)
            continue
        parts = str(row["time_of_day"]).strip().split(":")
        if len(parts) != 2:
            LOG.warning("Bad time_of_day for schedule %s", row["id"])
            continue
        hour_s, minute_s = parts[0], parts[1]
        try:
            hour, minute = int(hour_s), int(minute_s)
        except ValueError:
            LOG.warning("Bad time_of_day for schedule %s", row["id"])
            continue
        trigger = CronTrigger(
            hour=hour,
            minute=minute,
            day_of_week=_days_to_trigger(days),
        )
        target.add_job(
            _run_schedule,
            trigger=trigger,
            id=_job_id(int(row["id"])),
            replace_existing=True,
            kwargs={
                "device_id": int(row["device_id"]),
                "action": str(row["action"]),
                "schedule_id": int(row["id"]),
            },
        )
    LOG.info("Scheduler synced with %s active jobs", len(target.get_jobs()))


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.start()
    sync_scheduler_jobs(_scheduler)
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def notify_schedule_changed() -> None:
    if _scheduler is not None:
        sync_scheduler_jobs(_scheduler)
