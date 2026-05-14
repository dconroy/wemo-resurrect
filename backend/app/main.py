from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import init_db
from .routers import devices, discover, schedules
from .scheduler_service import shutdown_scheduler, start_scheduler

LOG = logging.getLogger(__name__)


def _configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    init_db()
    start_scheduler()
    LOG.info(
        "WeMo dashboard starting (uvicorn host=%s, WEMO_DASHBOARD_PORT=%s, bind_lan=%s)",
        get_settings().uvicorn_host,
        get_settings().dashboard_port,
        get_settings().dashboard_bind_lan,
    )
    yield
    shutdown_scheduler()
    LOG.info("WeMo dashboard stopped")


app = FastAPI(title="WeMo Resurrect", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(discover.router)
app.include_router(devices.router)
app.include_router(schedules.router)

_static = Path(__file__).resolve().parent / "static"
_assets = _static / "assets"
if _static.is_dir() and (_static / "index.html").is_file():
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/", include_in_schema=False)
    def serve_index() -> FileResponse:
        return FileResponse(_static / "index.html")
else:

    @app.get("/")
    def root_stub() -> dict[str, str]:
        return {
            "message": "API only — build the frontend into backend/app/static or open /docs",
        }
