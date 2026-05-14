from fastapi.testclient import TestClient


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_devices_empty(client):
    r = client.get("/api/devices")
    assert r.status_code == 200
    assert r.json() == []


def test_schedule_crud(client):
    from app import database as db

    with db.db_conn() as conn:
        row = db.upsert_device(
            conn,
            name="Test switch",
            ip="10.0.0.55",
            port=49153,
            model="Test",
            serial=None,
            udn="uuid:test-wemo-1",
        )
        did = int(row["id"])

    r = client.post(
        "/api/schedules",
        json={
            "device_id": did,
            "action": "off",
            "time_of_day": "23:30",
            "days_of_week": [0, 1, 2, 3, 4],
            "enabled": True,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["device_id"] == did
    assert body["action"] == "off"
    sid = body["id"]

    r2 = client.get("/api/schedules")
    assert r2.status_code == 200
    assert len(r2.json()) == 1

    r3 = client.put(f"/api/schedules/{sid}", json={"enabled": False})
    assert r3.status_code == 200
    assert r3.json()["enabled"] is False

    r4 = client.delete(f"/api/schedules/{sid}")
    assert r4.status_code == 200
    r5 = client.get("/api/schedules")
    assert r5.json() == []


def test_reads_require_auth_when_password_set(tmp_path, monkeypatch):
    monkeypatch.setenv("WEMO_DATABASE_PATH", str(tmp_path / "read.sqlite"))
    monkeypatch.setenv("WEMO_ADMIN_PASSWORD", "tok")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    try:
        with TestClient(app) as c:
            assert c.get("/api/devices").status_code == 401
            assert (
                c.get("/api/devices", headers={"Authorization": "Bearer tok"}).status_code
                == 200
            )
            assert c.get("/api/health").status_code == 200
    finally:
        get_settings.cache_clear()


def test_admin_password_blocks_mutations(tmp_path, monkeypatch):
    monkeypatch.setenv("WEMO_DATABASE_PATH", str(tmp_path / "auth.sqlite"))
    monkeypatch.setenv("WEMO_ADMIN_PASSWORD", "s3cret")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    try:
        with TestClient(app) as c:
            r = c.post("/api/discover")
            assert r.status_code == 401
            r2 = c.post("/api/discover", headers={"Authorization": "Bearer s3cret"})
            assert r2.status_code in (200, 502)
    finally:
        get_settings.cache_clear()

