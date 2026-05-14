# WeMo Resurrect

<p align="center">
  <img src="logo.png" alt="WeMo Resurrect logo" width="360" />
</p>

Local-only web dashboard to discover and control legacy Belkin **WeMo** switches and plugs over the LAN using **UPnP / SSDP discovery** and **local SOAP** (via [pywemo](https://github.com/pywemo/pywemo), with a small **BasicEvent SOAP fallback**). There is **no Belkin cloud**, mobile app, Alexa, or Google Home dependency.

## Features

- **Discovery** over SSDP/UPnP, plus **manual add by IPv4** when discovery is unreliable.
- **SQLite** persistence for devices and schedules (survives restarts).
- **ON / OFF / refresh** using local control only, with **retries** and clear offline handling.
- **Recurring schedules** (time of day + weekdays) using **APScheduler** in the **server’s local timezone**.
- **FastAPI** REST API and a small **React + Vite** UI served from the same process once built into `backend/app/static/`.
- **Security defaults**: binds to **localhost** unless you opt into LAN binding; optional **`WEMO_ADMIN_PASSWORD`** (Bearer token) for **all** API routes except `GET /api/health`.

## Requirements

- Python **3.11+** (Docker image uses **3.12**).
- Node **20+** (only needed to build the frontend).
- Your machine on the **same LAN** as the WeMo devices. Firewalls must allow SSDP multicast and HTTP to the plugs (typically ports like **49152–49153**).

## Quick start (development)

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env          # optional: edit values

# Terminal 1 — API + built UI (after frontend build, see below)
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8765
```

Build the UI once (output is copied where uvicorn serves it). **Prebuilt assets are included** under `backend/app/static/`; repeat this step only after you change the frontend:

```bash
cd frontend
npm install
npm run build
mkdir -p ../backend/app/static
rm -rf ../backend/app/static/*
cp -r dist/* ../backend/app/static/
```

Open **http://127.0.0.1:8765/**. API docs: **http://127.0.0.1:8765/docs**.

For UI development with hot reload:

```bash
cd frontend
npm run dev
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8765` (run uvicorn separately).

## Configuration (environment variables)

| Variable | Default | Description |
| --- | --- | --- |
| `WEMO_DASHBOARD_HOST` | `127.0.0.1` | Address uvicorn binds when **not** using LAN bind. |
| `WEMO_DASHBOARD_PORT` | `8765` | HTTP port. |
| `WEMO_DASHBOARD_BIND_LAN` | `0` | Set to `1` / `true` to listen on **0.0.0.0** (all interfaces) for Pi / NAS use. |
| `WEMO_ADMIN_PASSWORD` | _(empty)_ | If set, **all** `/api/*` routes except `GET /api/health` require `Authorization: Bearer <password>`. |
| `WEMO_DATABASE_PATH` | `data/wemo_dashboard.db` | SQLite file path (relative to the **current working directory** when you start uvicorn). |
| `WEMO_LOG_LEVEL` | `INFO` | Python log level. |

**Never** expose this service directly to the public Internet. Use it on a trusted home LAN, or put it behind a VPN or reverse proxy you control.

## REST API (summary)

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness check. |
| `GET` | `/api/devices` | List stored devices. |
| `POST` | `/api/discover` | Run SSDP discovery and merge into SQLite. |
| `POST` | `/api/devices/manual` | Body: `{ "ip": "…", "name": "…?" }`. |
| `GET` | `/api/devices/{id}/status` | Poll live state. |
| `POST` | `/api/devices/{id}/on` | Turn on. |
| `POST` | `/api/devices/{id}/off` | Turn off. |
| `GET` | `/api/schedules` | Optional query parameter `device_id` to filter. |
| `POST` | `/api/schedules` | Create schedule. |
| `PUT` | `/api/schedules/{id}` | Update. |
| `DELETE` | `/api/schedules/{id}` | Delete. |

Schedules use **`days_of_week`**: integers **0 = Monday** through **6 = Sunday**, matching APScheduler’s `day_of_week` convention.

## Docker

```bash
docker compose up --build
```

Data is stored in the **`wemo-data`** Docker volume at `WEMO_DATABASE_PATH` (`/data/wemo_dashboard.db` in the compose file).

## Tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

## Project layout

- `backend/app/` — FastAPI app, SQLite access, `wemo_client.py`, scheduler.
- `frontend/` — Vite + React dashboard.
- `Dockerfile` / `docker-compose.yml` — single container serving API + static UI.

## Troubleshooting

- **Discovery finds nothing:** try **Add by IP** from the device’s IPv4 address; ensure your OS firewall allows multicast UDP for SSDP.
- **Control fails intermittently:** the app retries pywemo calls; extremely old firmware may work better after a power cycle.
- **Unsupported WeMo models:** pywemo may still discover them with `debug=True` (not wired in the UI); the SOAP fallback only covers classic **BinaryState** switch-style control.

## License

Use and modify for personal home use. Third-party libraries (FastAPI, pywemo, etc.) remain under their respective licenses.
