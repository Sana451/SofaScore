from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
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
