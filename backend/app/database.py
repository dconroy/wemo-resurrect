from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from .config import get_settings

LOG = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _db_path() -> Path:
    p = get_settings().database_path
    return p if p.is_absolute() else Path.cwd() / p


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    path = _db_path()
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              id INTEGER PRIMARY KEY,
              version INTEGER NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS devices (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              ip TEXT NOT NULL,
              port INTEGER,
              model TEXT,
              serial TEXT,
              udn TEXT NOT NULL UNIQUE,
              last_seen TEXT NOT NULL,
              last_state INTEGER,
              last_state_at TEXT,
              online INTEGER NOT NULL DEFAULT 0,
              last_error TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_devices_ip ON devices(ip);

            CREATE TABLE IF NOT EXISTS schedules (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              device_id INTEGER NOT NULL,
              action TEXT NOT NULL CHECK (action IN ('on', 'off')),
              time_of_day TEXT NOT NULL,
              days_of_week TEXT NOT NULL,
              enabled INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_schedules_device ON schedules(device_id);
            """
        )
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        current = int(row[0] or 0)
        if current < 1:
            conn.execute(
                "INSERT INTO schema_migrations (id, version) VALUES (1, 1) "
                "ON CONFLICT(version) DO NOTHING"
            )
        conn.commit()
    LOG.info("Database initialized at %s", path)


@contextmanager
def db_conn() -> Generator[sqlite3.Connection, None, None]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def list_devices(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    cur = conn.execute(
        "SELECT * FROM devices ORDER BY name COLLATE NOCASE ASC, id ASC"
    )
    return [row_to_dict(r) for r in cur.fetchall()]


def get_device(conn: sqlite3.Connection, device_id: int) -> dict[str, Any] | None:
    cur = conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,))
    row = cur.fetchone()
    return row_to_dict(row) if row else None


def upsert_device(
    conn: sqlite3.Connection,
    *,
    name: str,
    ip: str,
    port: int | None,
    model: str | None,
    serial: str | None,
    udn: str,
) -> dict[str, Any]:
    now = _utc_now_iso()
    conn.execute(
        """
        INSERT INTO devices (
          name, ip, port, model, serial, udn, last_seen, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(udn) DO UPDATE SET
          name = excluded.name,
          ip = excluded.ip,
          port = COALESCE(excluded.port, devices.port),
          model = COALESCE(excluded.model, devices.model),
          serial = COALESCE(excluded.serial, devices.serial),
          last_seen = excluded.last_seen,
          updated_at = excluded.updated_at
        """,
        (name, ip, port, model, serial, udn, now, now, now),
    )
    cur = conn.execute("SELECT * FROM devices WHERE udn = ?", (udn,))
    row = cur.fetchone()
    assert row is not None
    return row_to_dict(row)


def update_device_status(
    conn: sqlite3.Connection,
    device_id: int,
    *,
    online: bool,
    last_state: int | None,
    last_error: str | None,
) -> None:
    now = _utc_now_iso()
    if online:
        if last_state is not None:
            conn.execute(
                """
                UPDATE devices SET
                  online = 1,
                  last_state = ?,
                  last_state_at = ?,
                  last_error = ?,
                  updated_at = ?
                WHERE id = ?
                """,
                (last_state, now, last_error, now, device_id),
            )
        else:
            conn.execute(
                """
                UPDATE devices SET online = 1, last_error = ?, updated_at = ? WHERE id = ?
                """,
                (last_error, now, device_id),
            )
    else:
        conn.execute(
            """
            UPDATE devices SET online = 0, last_error = ?, updated_at = ? WHERE id = ?
            """,
            (last_error, now, device_id),
        )


def list_schedules(conn: sqlite3.Connection, device_id: int | None = None) -> list[dict[str, Any]]:
    if device_id is None:
        cur = conn.execute(
            "SELECT * FROM schedules ORDER BY device_id ASC, time_of_day ASC, id ASC"
        )
    else:
        cur = conn.execute(
            "SELECT * FROM schedules WHERE device_id = ? ORDER BY time_of_day ASC, id ASC",
            (device_id,),
        )
    return [row_to_dict(r) for r in cur.fetchall()]


def get_schedule(conn: sqlite3.Connection, schedule_id: int) -> dict[str, Any] | None:
    cur = conn.execute("SELECT * FROM schedules WHERE id = ?", (schedule_id,))
    row = cur.fetchone()
    return row_to_dict(row) if row else None


def create_schedule(
    conn: sqlite3.Connection,
    *,
    device_id: int,
    action: str,
    time_of_day: str,
    days_of_week: list[int],
    enabled: bool,
) -> dict[str, Any]:
    now = _utc_now_iso()
    days_json = json.dumps(days_of_week)
    cur = conn.execute(
        """
        INSERT INTO schedules (device_id, action, time_of_day, days_of_week, enabled, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (device_id, action, time_of_day, days_json, 1 if enabled else 0, now, now),
    )
    sid = int(cur.lastrowid)
    row = get_schedule(conn, sid)
    assert row is not None
    return row


def update_schedule(
    conn: sqlite3.Connection,
    schedule_id: int,
    *,
    device_id: int | None = None,
    action: str | None = None,
    time_of_day: str | None = None,
    days_of_week: list[int] | None = None,
    enabled: bool | None = None,
) -> dict[str, Any] | None:
    row = get_schedule(conn, schedule_id)
    if not row:
        return None
    now = _utc_now_iso()
    new_device = device_id if device_id is not None else row["device_id"]
    new_action = action if action is not None else row["action"]
    new_time = time_of_day if time_of_day is not None else row["time_of_day"]
    new_days = json.dumps(days_of_week) if days_of_week is not None else row["days_of_week"]
    new_enabled = (1 if enabled else 0) if enabled is not None else row["enabled"]
    conn.execute(
        """
        UPDATE schedules SET
          device_id = ?, action = ?, time_of_day = ?, days_of_week = ?, enabled = ?, updated_at = ?
        WHERE id = ?
        """,
        (new_device, new_action, new_time, new_days, new_enabled, now, schedule_id),
    )
    return get_schedule(conn, schedule_id)


def delete_schedule(conn: sqlite3.Connection, schedule_id: int) -> bool:
    cur = conn.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
    return cur.rowcount > 0


def parse_days_json(days_s: str) -> list[int]:
    data = json.loads(days_s)
    if not isinstance(data, list):
        raise ValueError("days_of_week must be a list")
    out: list[int] = []
    for x in data:
        if not isinstance(x, int) or x < 0 or x > 6:
            raise ValueError("each weekday must be int 0-6 (Mon=0 .. Sun=6)")
        out.append(x)
    return sorted(set(out))
