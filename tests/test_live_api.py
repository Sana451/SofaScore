from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "live_payload.json"


def make_client() -> TestClient:
    temp_dir = tempfile.TemporaryDirectory()
    db_path = Path(temp_dir.name) / "test.db"
    settings = Settings(db_path=db_path, fixture_path=FIXTURE, auto_seed=True)
    app = create_app(settings)
    client = TestClient(app)
    client._temp_dir = temp_dir  # type: ignore[attr-defined]
    return client


def test_live_endpoint_filters_editor_events() -> None:
    with make_client() as client:
        response = client.get("/api/v1/sport/football/events/live")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"events"}
    assert len(payload["events"]) == 2
    assert all(event["status"] == "LIVE" for event in payload["events"])
    assert all(event["isEditor"] is False for event in payload["events"])
    assert {event["id"] for event in payload["events"]} == {5001, 5003}


def test_swagger_lists_live_endpoint() -> None:
    with make_client() as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    openapi = response.json()
    assert "/api/v1/sport/football/events/live" in openapi["paths"]


def test_startup_seeds_database_once() -> None:
    with make_client() as client:
        first = client.get("/api/v1/sport/football/events/live")
        second = client.get("/api/v1/sport/football/events/live")
    assert first.json() == second.json()


def test_startup_logs_fixture_mode(caplog) -> None:
    with caplog.at_level("INFO"):
        with make_client() as client:
            client.get("/api/v1/sport/football/events/live")

    assert any("Starting application: mode=fixture" in record.message for record in caplog.records)
    assert any("football-data polling disabled" in record.message for record in caplog.records)


def test_get_settings_auto_loads_dotenv(tmp_path, monkeypatch) -> None:
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "SOFASCORE_DB_PATH=./from-dotenv.db",
                "SOFASCORE_LOG_LEVEL=DEBUG",
                "SOFASCORE_FOOTBALL_DATA_TOKEN=dotenv-token",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.config.BASE_DIR", tmp_path)
    monkeypatch.delenv("SOFASCORE_DB_PATH", raising=False)
    monkeypatch.delenv("SOFASCORE_LOG_LEVEL", raising=False)
    monkeypatch.delenv("SOFASCORE_FOOTBALL_DATA_TOKEN", raising=False)

    settings = get_settings()

    assert settings.db_path == Path("from-dotenv.db")
    assert settings.log_level == "DEBUG"
    assert settings.football_data_token == "dotenv-token"
