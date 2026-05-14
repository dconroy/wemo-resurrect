from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class DeviceOut(BaseModel):
    id: int
    name: str
    ip: str
    port: int | None = None
    model: str | None = None
    serial: str | None = None
    udn: str
    last_seen: str
    last_state: int | None = None
    last_state_at: str | None = None
    online: bool
    last_error: str | None = None


class ManualDeviceIn(BaseModel):
    ip: str = Field(..., description="IPv4 address of the WeMo on your LAN")
    name: str | None = Field(None, description="Optional friendly name override")

    @field_validator("ip")
    @classmethod
    def ip_ok(cls, v: str) -> str:
        s = v.strip()
        if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", s):
            raise ValueError("ip must be an IPv4 address")
        return s


class ScheduleCreate(BaseModel):
    device_id: int
    action: Literal["on", "off"]
    time_of_day: str
    days_of_week: list[int] = Field(..., min_length=1)
    enabled: bool = True

    @field_validator("days_of_week")
    @classmethod
    def days_ok(cls, v: list[int]) -> list[int]:
        for d in v:
            if d < 0 or d > 6:
                raise ValueError("weekdays must be 0-6 (Mon=0 .. Sun=6)")
        return sorted(set(v))

    @field_validator("time_of_day")
    @classmethod
    def time_ok(cls, v: str) -> str:
        h, m = v.split(":")
        hi, mi = int(h), int(m)
        if hi < 0 or hi > 23 or mi < 0 or mi > 59:
            raise ValueError("invalid time_of_day")
        return f"{hi:02d}:{mi:02d}"


class ScheduleUpdate(BaseModel):
    device_id: int | None = None
    action: Literal["on", "off"] | None = None
    time_of_day: str | None = None
    days_of_week: list[int] | None = None
    enabled: bool | None = None

    @field_validator("days_of_week")
    @classmethod
    def days_ok(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return v
        for d in v:
            if d < 0 or d > 6:
                raise ValueError("weekdays must be 0-6 (Mon=0 .. Sun=6)")
        return sorted(set(v))

    @field_validator("time_of_day")
    @classmethod
    def time_ok(cls, v: str | None) -> str | None:
        if v is None:
            return v
        h, m = v.split(":")
        hi, mi = int(h), int(m)
        if hi < 0 or hi > 23 or mi < 0 or mi > 59:
            raise ValueError("invalid time_of_day")
        return f"{hi:02d}:{mi:02d}"


class ScheduleOut(BaseModel):
    id: int
    device_id: int
    action: str
    time_of_day: str
    days_of_week: list[int]
    enabled: bool
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: dict) -> ScheduleOut:
        days = json.loads(row["days_of_week"])
        return cls(
            id=int(row["id"]),
            device_id=int(row["device_id"]),
            action=str(row["action"]),
            time_of_day=str(row["time_of_day"]),
            days_of_week=days,
            enabled=bool(row["enabled"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )


class StatusOut(BaseModel):
    device_id: int
    online: bool
    last_state: int | None
    last_state_at: str | None = None
    last_error: str | None = None


def device_from_row(row: dict) -> DeviceOut:
    return DeviceOut(
        id=int(row["id"]),
        name=str(row["name"]),
        ip=str(row["ip"]),
        port=row["port"],
        model=row["model"],
        serial=row["serial"],
        udn=str(row["udn"]),
        last_seen=str(row["last_seen"]),
        last_state=row["last_state"],
        last_state_at=row["last_state_at"],
        online=bool(row["online"]),
        last_error=row["last_error"],
    )
