from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from typing import Iterator

from fastapi import Depends, FastAPI, Request

from .config import Settings, get_settings
from .db import connect, fetch_live_events, initialize_database
from .schemas import LiveEventsResponse


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
    initialize_database(settings)
    yield


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
