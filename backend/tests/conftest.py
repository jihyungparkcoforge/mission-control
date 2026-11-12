import pytest

from app.config import Settings
from app.db import Database
from app.llm import FakeModelClient
from app.pipeline import Pipeline

FD = {"X-FD-Token": "test-fd-token"}

GOOD = {"name": "Ana Ortiz", "station": "PROP-2", "wind_knots": 12, "temp_c": 15, "fuel_pct": 99,
        "note": "LOX fill valve V-12 took 2.1 s to close at T-95, nominal is 1.5 s. Second cycle normal."}


@pytest.fixture
def settings(tmp_path):
    # No API key -> demo/fake mode; nothing in tests can reach the network.
    return Settings(db_path=str(tmp_path / "mc.db"), openai_api_key=None, fd_token="test-fd-token")


@pytest.fixture
def make_client(settings):
    def _make(fake: FakeModelClient | None = None):
        from fastapi.testclient import TestClient

        from app.main import create_app
        return TestClient(create_app(settings, fake or FakeModelClient()))
    return _make


@pytest.fixture
def make_pipeline(settings):
    def _make(fake: FakeModelClient) -> tuple[Pipeline, Database]:
        db = Database(settings.db_path)
        return Pipeline(db, fake, settings), db
    return _make
