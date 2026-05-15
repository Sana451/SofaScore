from __future__ import annotations

import asyncio
import logging
import sqlite3
from contextlib import asynccontextmanager, suppress
from typing import Iterator

from fastapi import Depends, FastAPI, Request

from .config import Settings, get_settings
from .db import connect, fetch_live_events, initialize_database
from .logging_utils import configure_logging
from .poller import run_football_data_poller
from .schemas import LiveEventsResponse

LOGGER = logging.getLogger(__name__)


def get_db_connection(request: Request) -> Iterator[sqlite3.Connection]:
    settings: Settings = request.app.state.settings
    connection = connect(settings.db_path)
    try:
        yield connection
    finally:
        connection.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    configure_logging(settings.log_level)
    LOGGER.info(
        "Starting application: mode=%s db=%s fixture=%s auto_seed=%s log_level=%s",
        settings.runtime_mode,
        settings.db_path,
        settings.fixture_path,
        settings.should_seed_fixture,
        settings.log_level.upper(),
    )
    initialize_database(settings)
    poller_task: asyncio.Task[None] | None = None
    if settings.polling_enabled:
        LOGGER.info(
            "football-data polling enabled: base_url=%s competitions=%s interval=%ss timeout=%ss",
            settings.football_data_base_url,
            settings.football_data_competitions or "ALL",
            settings.football_data_poll_interval_seconds,
            settings.football_data_timeout_seconds,
        )
        poller_task = asyncio.create_task(run_football_data_poller(settings))
    else:
        LOGGER.info("football-data polling disabled: fixture mode is active")
    try:
        yield
    finally:
        if poller_task is not None:
            LOGGER.info("Stopping football-data poller")
            poller_task.cancel()
            with suppress(asyncio.CancelledError):
                await poller_task


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    app = FastAPI(
        title="Mini SofaScore-like football service",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.state.settings = resolved_settings

    @app.get(
        "/api/v1/sport/football/events/live",
        response_model=LiveEventsResponse,
        tags=["football"],
        summary="Live football events",
        description=(
            "Public live feed built from normalized tables; editor events are filtered out."
        ),
    )
    def live_events(db: sqlite3.Connection = Depends(get_db_connection)) -> dict[str, object]:
        return {"events": fetch_live_events(db)}

    return app


app = create_app()
