from __future__ import annotations

import asyncio
import logging
import time

import httpx

from .config import Settings
from .db import connect, ingest_football_data_payload
from .sources.football_data import build_live_matches_url

LOGGER = logging.getLogger(__name__)


async def fetch_live_payload(settings: Settings, client: httpx.AsyncClient | None = None) -> str:
    if not settings.football_data_token:
        raise RuntimeError("football-data token is not configured")

    close_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            base_url=settings.football_data_base_url,
            timeout=settings.football_data_timeout_seconds,
            headers={"X-Auth-Token": settings.football_data_token},
        )

    try:
        response = await client.get(
            "/v4/matches",
            params={"status": "LIVE", **_competition_params(settings)},
        )
        response.raise_for_status()
        return response.text
    finally:
        if close_client:
            await client.aclose()


async def poll_football_data_once(
    settings: Settings, client: httpx.AsyncClient | None = None
) -> int:
    source = build_live_matches_url(
        settings.football_data_base_url, settings.football_data_competitions
    )
    LOGGER.info("football-data poll started: source=%s", source)
    started_at = time.perf_counter()
    raw_payload = await fetch_live_payload(settings, client=client)
    with connect(settings.db_path) as conn:
        raw_snapshot_id = ingest_football_data_payload(conn, raw_payload, source=source)
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    LOGGER.info(
        "football-data poll completed: raw_snapshot_id=%s elapsed_ms=%.1f",
        raw_snapshot_id,
        elapsed_ms,
    )
    return raw_snapshot_id


async def run_football_data_poller(settings: Settings) -> None:
    if not settings.football_data_token:
        return

    LOGGER.info(
        "Starting football-data poller: interval=%ss source=%s",
        settings.football_data_poll_interval_seconds,
        build_live_matches_url(
            settings.football_data_base_url, settings.football_data_competitions
        ),
    )

    while True:
        try:
            await poll_football_data_once(settings)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("football-data polling failed")
        await asyncio.sleep(settings.football_data_poll_interval_seconds)


def _competition_params(settings: Settings) -> dict[str, str]:
    if settings.football_data_competitions:
        return {"competitions": settings.football_data_competitions}
    return {}
