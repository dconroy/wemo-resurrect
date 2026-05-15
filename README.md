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

- **Recommended:** [Docker](https://docs.docker.com/get-docker/) with the **Compose** plugin (Docker Desktop includes it). No Python or Node on your machine.
- **Optional — local development:** Python **3.11+**, Node **20+** (only if you want to edit code without rebuilding the image).
- Your machine on the **same LAN** as the WeMo devices. Firewalls must allow SSDP multicast and HTTP to the plugs (typically ports like **49152–49153**).

## Quick start (Docker — one terminal)

From the repository root, everything (API, UI, SQLite path inside the container) runs in **one container**:

```bash
cp .env.example .env   # optional: set WEMO_ADMIN_PASSWORD, WEMO_LOG_LEVEL, etc.

docker compose up --build
```

Then open **http://127.0.0.1:8765/** on the same machine, or use your host’s LAN IP and port **8765** from a phone or tablet on the same Wi‑Fi. API docs: **http://127.0.0.1:8765/docs**.

- **Foreground (logs in this terminal):** `docker compose up --build`
- **Background (detach, still one command to start):** `docker compose up --build -d` — follow logs with `docker compose logs -f`

The image builds the React app and bakes it into the container; SQLite lives in the **`wemo-data`** volume (path inside the container defaults to `/data/wemo_dashboard.db`).

### Docker Desktop on Mac (reach the dashboard from your LAN)

1. From the repo root: `cp .env.example .env` (optional), then **`docker compose up --build`**.
2. The compose file publishes **`8765`** on your Mac. Other devices use **`http://<your-mac-lan-ip>:8765`** (same Wi‑Fi as the Mac). Find the IP under **System Settings → Network**, or run `ipconfig getifaddr en0` (often Wi‑Fi).
3. If the Mac firewall blocks inbound connections, allow **Docker** / **com.docker.backend** for port **8765**, or temporarily allow incoming for local testing.
4. **SSDP “Discover devices”** from inside Docker on Mac often still finds **nothing** (multicast + Docker Desktop limits). That is normal. Use **Add by IP** with each WeMo’s **IPv4**; **on/off** and schedules use direct HTTP to the plug and usually work fine once the device is saved.
5. **`docker-compose.host-network.yml`** does **not** give real Linux-style host networking on Mac; Docker Desktop ignores it for SSDP. For reliable discovery without “Add by IP”, run **`uvicorn` on the Mac host** (see “Optional: local development”) instead of Docker.

### Docker notes

- **SSDP discovery inside Docker** often sees **zero devices** because multicast does not cross the default bridge network the same way as on your host LAN. The UI now shows an explicit message after each scan. Mitigations: use **Add by IP**, or on **Linux** run with host networking:
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.host-network.yml up --build
  ```
  (`docker-compose.host-network.yml` is in the repo root.) Host networking behaves differently on **Docker Desktop for Mac/Windows**; prefer **Add by IP** there if discovery is empty.
- **Never** expose port 8765 directly to the public Internet.

## Configuration (environment variables)

Set these in a **`.env`** file next to `docker-compose.yml` (Compose uses it for `${VAR}` substitution), or export them in your shell before `docker compose up`.

| Variable | Default (in compose) | Description |
| --- | --- | --- |
| `WEMO_DATABASE_PATH` | `/data/wemo_dashboard.db` | SQLite path **inside the container** (backed by the `wemo-data` volume). |
| `WEMO_LOG_LEVEL` | `INFO` | Python log level. |
| `WEMO_ADMIN_PASSWORD` | _(empty)_ | If set, **all** `/api/*` routes except `GET /api/health` require `Authorization: Bearer <password>`. |
| `WEMO_DISCOVERY_SSDP_TIMEOUT` | `15` in compose (`12` in `.env.example`) | Seconds to listen for SSDP replies during discovery (3–120). |

When running **without** Docker (`uvicorn` locally), you can also use:

| Variable | Default | Description |
| --- | --- | --- |
| `WEMO_DASHBOARD_HOST` | `127.0.0.1` | Address uvicorn binds when **not** using LAN bind. |
| `WEMO_DASHBOARD_PORT` | `8765` | HTTP port (must match how you launch uvicorn). |
| `WEMO_DASHBOARD_BIND_LAN` | `0` | Set to `1` / `true` to listen on **0.0.0.0** (all interfaces) for Pi / NAS use. |

The Docker image sets **`WEMO_DASHBOARD_BIND_LAN=1`** so the app listens on all interfaces inside the container; you still reach it via the published host port (**8765**).

**Never** expose this service directly to the public Internet. Use it on a trusted home LAN, or put it behind a VPN or reverse proxy you control.

## Optional: local development (no Docker)

Use this only if you are changing Python or frontend code and want faster iteration than `docker compose build`.

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env          # optional: edit values

cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8765
```

After **frontend** changes, rebuild static assets (prebuilt copies exist under `backend/app/static/` until you change the UI):

```bash
cd frontend
npm install
npm run build
rm -rf ../backend/app/static && mkdir -p ../backend/app/static && cp -r dist/. ../backend/app/static/
```

If you use the Vite dev server with hot reload, that is a **second** terminal (`npm run dev` in `frontend/`, with uvicorn still running for `/api`).

## REST API (summary)

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness check. |
| `GET` | `/api/devices` | List stored devices. |
| `POST` | `/api/discover` | Returns `{ devices, discovered_this_run, message }`. SSDP often returns 0 devices inside Docker (see README). |
| `POST` | `/api/devices/manual` | Body: `{ "ip": "…", "name": "…?" }`. |
| `GET` | `/api/devices/{id}/status` | Poll live state. |
| `POST` | `/api/devices/{id}/on` | Turn on. |
| `POST` | `/api/devices/{id}/off` | Turn off. |
| `GET` | `/api/schedules` | Optional query parameter `device_id` to filter. |
| `POST` | `/api/schedules` | Create schedule. |
| `PUT` | `/api/schedules/{id}` | Update. |
| `DELETE` | `/api/schedules/{id}` | Delete. |

Schedules use **`days_of_week`**: integers **0 = Monday** through **6 = Sunday**, matching APScheduler’s `day_of_week` convention.

## Tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

## Project layout

- `backend/app/` — FastAPI app, SQLite access, `wemo_client.py`, scheduler.
- `frontend/` — Vite + React dashboard.
- `Dockerfile` / `docker-compose.yml` / `docker-compose.host-network.yml` — single container serving API + static UI; optional Linux host network for SSDP.

## Troubleshooting

- **Discovery finds nothing:** try **Add by IP** from the device’s IPv4 address; ensure your OS firewall allows multicast UDP for SSDP. From Docker, try host networking on Linux if needed.
- **Control fails intermittently:** the app retries pywemo calls; extremely old firmware may work better after a power cycle.
- **Unsupported WeMo models:** pywemo may still discover them with `debug=True` (not wired in the UI); the SOAP fallback only covers classic **BinaryState** switch-style control.

## License

Use and modify for personal home use. Third-party libraries (FastAPI, pywemo, etc.) remain under their respective licenses.
