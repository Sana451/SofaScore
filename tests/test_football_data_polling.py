from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connect, fetch_live_events, initialize_database
from app.main import create_app
from app.poller import poll_football_data_once

ROOT = Path(__file__).resolve().parents[1]

FOOTBALL_DATA_SAMPLE = {
    "matches": [
        {
            "id": 9001,
            "status": "IN_PLAY",
            "utcDate": "2026-05-15T12:30:00Z",
            "competition": {
                "id": 100,
                "name": "Premier League",
                "code": "PL",
                "area": {"name": "England"},
            },
            "homeTeam": {"id": 11, "name": "Arsenal", "tla": "ARS"},
            "awayTeam": {"id": 12, "name": "Chelsea", "tla": "CHE"},
            "score": {"current": {"home": 2, "away": 1}},
            "venue": {"name": "Emirates Stadium"},
        },
        {
            "id": 9002,
            "status": "FINISHED",
            "utcDate": "2026-05-15T10:00:00Z",
            "competition": {
                "id": 100,
                "name": "Premier League",
                "code": "PL",
                "area": {"name": "England"},
            },
            "homeTeam": {"id": 13, "name": "Liverpool", "tla": "LIV"},
            "awayTeam": {"id": 14, "name": "Manchester City", "tla": "MCI"},
            "score": {"fullTime": {"home": 0, "away": 0}},
            "venue": {"name": "Anfield"},
        },
    ]
}


def make_settings(*, token: str | None = None) -> tuple[Settings, tempfile.TemporaryDirectory[str]]:
    temp_dir = tempfile.TemporaryDirectory()
    settings = Settings(
        db_path=Path(temp_dir.name) / "test.db",
        fixture_path=ROOT / "fixtures" / "live_payload.json",
        auto_seed=False,
        football_data_token=token,
        football_data_base_url="https://api.football-data.org",
        football_data_competitions="PL",
        football_data_poll_interval_seconds=1,
        football_data_timeout_seconds=1.0,
    )
    return settings, temp_dir


async def _poll_once_with_mock_transport(settings: Settings) -> int:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-auth-token"] == "secret-token"
        assert request.url.path == "/v4/matches"
        assert request.url.params["status"] == "LIVE"
        assert request.url.params["competitions"] == "PL"
        return httpx.Response(200, json=FOOTBALL_DATA_SAMPLE)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url=settings.football_data_base_url,
        transport=transport,
        headers={"X-Auth-Token": settings.football_data_token or ""},
    ) as client:
        return await poll_football_data_once(settings, client=client)


def test_real_payload_ingests_into_normalized_tables() -> None:
    settings, temp_dir = make_settings(token="secret-token")
    try:
        initialize_database(settings)
        raw_snapshot_id = asyncio.run(_poll_once_with_mock_transport(settings))
        assert raw_snapshot_id == 1

        with connect(settings.db_path) as conn:
            live_events = fetch_live_events(conn)

        assert len(live_events) == 1
        assert live_events[0]["id"] == 9001
        assert live_events[0]["status"] == "LIVE"
        assert live_events[0]["scores"] == {"home": 2, "away": 1}
        assert live_events[0]["isEditor"] is False
    finally:
        temp_dir.cleanup()


def test_public_api_works_in_polling_mode_from_normalized_db(monkeypatch) -> None:
    settings, temp_dir = make_settings(token="secret-token")
    try:
        initialize_database(settings)
        asyncio.run(_poll_once_with_mock_transport(settings))

        async def noop_poller(_: Settings) -> None:
            return None

        monkeypatch.setattr("app.main.run_football_data_poller", noop_poller)
        app = create_app(settings)
        with TestClient(app) as client:
            response = client.get("/api/v1/sport/football/events/live")

        assert response.status_code == 200
        payload = response.json()
        assert set(payload.keys()) == {"events"}
        assert len(payload["events"]) == 1
        assert payload["events"][0]["id"] == 9001
        assert payload["events"][0]["status"] == "LIVE"
    finally:
        temp_dir.cleanup()


def test_polling_cycle_logs_activity(caplog) -> None:
    settings, temp_dir = make_settings(token="secret-token")
    try:
        initialize_database(settings)
        with caplog.at_level("INFO"):
            asyncio.run(_poll_once_with_mock_transport(settings))

        assert any("football-data poll started" in record.message for record in caplog.records)
        assert any("football-data poll completed" in record.message for record in caplog.records)
    finally:
        temp_dir.cleanup()
