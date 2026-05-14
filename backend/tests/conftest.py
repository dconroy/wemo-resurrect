import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("WEMO_DATABASE_PATH", str(tmp_path / "test.sqlite"))
    monkeypatch.delenv("WEMO_ADMIN_PASSWORD", raising=False)
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    get_settings.cache_clear()
