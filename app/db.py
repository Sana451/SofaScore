from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings
from .sources.football_data import normalize_football_data_payload

BASE_DIR = Path(__file__).resolve().parents[1]
MIGRATION_PATH = BASE_DIR / "migrations" / "001_init.sql"


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def apply_migrations(conn: sqlite3.Connection) -> None:
    conn.executescript(MIGRATION_PATH.read_text(encoding="utf-8"))
    conn.commit()


def database_is_empty(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT COUNT(*) AS count FROM raw_snapshots").fetchone()
    return int(row["count"]) == 0


def initialize_database(settings: Settings) -> None:
    with connect(settings.db_path) as conn:
        apply_migrations(conn)
        if settings.should_seed_fixture and database_is_empty(conn):
            seed_from_fixture(conn, settings.fixture_path)


def seed_from_fixture(conn: sqlite3.Connection, fixture_path: Path) -> int:
    raw_payload = fixture_path.read_text(encoding="utf-8")
    return ingest_raw_payload(conn, raw_payload, source=f"fixture:{fixture_path.name}")


def ingest_raw_payload(conn: sqlite3.Connection, raw_payload: str, source: str) -> int:
    payload = json.loads(raw_payload)
    normalized_events = []
    for event in payload.get("events", []):
        normalized_events.append(
            {
                "external_id": int(event["id"]),
                "slug": event["slug"],
                "status": str(event["status"]),
                "period": event.get("period"),
                "minute": event.get("minute"),
                "home_score": int((event.get("scores") or {}).get("home", 0)),
                "away_score": int((event.get("scores") or {}).get("away", 0)),
                "start_time": event["startTime"],
                "is_editor": bool(event.get("isEditor")),
                "venue_name": event.get("venueName"),
                "league": event["league"],
                "home_team": event["homeTeam"],
                "away_team": event["awayTeam"],
            }
        )
    return ingest_normalized_events(conn, raw_payload, source, normalized_events)


def ingest_football_data_payload(conn: sqlite3.Connection, raw_payload: str, source: str) -> int:
    payload = json.loads(raw_payload)
    normalized_events = normalize_football_data_payload(payload)
    return ingest_normalized_events(conn, raw_payload, source, normalized_events)


def ingest_normalized_events(
    conn: sqlite3.Connection,
    raw_payload: str,
    source: str,
    events: list[dict[str, Any]],
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO raw_snapshots (source, ingested_at, payload) VALUES (?, ?, ?)",
        (source, now, raw_payload),
    )
    raw_snapshot_id = int(cursor.lastrowid)

    for event in events:
        league_id = upsert_league(conn, event["league"], now)
        home_team_id = upsert_team(conn, event["home_team"], now)
        away_team_id = upsert_team(conn, event["away_team"], now)
        upsert_event(
            conn,
            raw_snapshot_id=raw_snapshot_id,
            league_id=league_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            event=event,
            updated_at=now,
        )

    conn.commit()
    return raw_snapshot_id


def upsert_league(conn: sqlite3.Connection, league: dict[str, Any], updated_at: str) -> int:
    external_id = int(league["id"])
    conn.execute(
        """
        INSERT INTO leagues (external_id, name, country, slug, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(external_id) DO UPDATE SET
            name = excluded.name,
            country = excluded.country,
            slug = excluded.slug,
            updated_at = excluded.updated_at
        """,
        (
            external_id,
            league["name"],
            league.get("country"),
            league.get("slug"),
            updated_at,
        ),
    )
    row = conn.execute("SELECT id FROM leagues WHERE external_id = ?", (external_id,)).fetchone()
    return int(row["id"])


def upsert_team(conn: sqlite3.Connection, team: dict[str, Any], updated_at: str) -> int:
    external_id = int(team["id"])
    conn.execute(
        """
        INSERT INTO teams (external_id, name, short_name, country, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(external_id) DO UPDATE SET
            name = excluded.name,
            short_name = excluded.short_name,
            country = excluded.country,
            updated_at = excluded.updated_at
        """,
        (
            external_id,
            team["name"],
            team.get("shortName"),
            team.get("country"),
            updated_at,
        ),
    )
    row = conn.execute("SELECT id FROM teams WHERE external_id = ?", (external_id,)).fetchone()
    return int(row["id"])


def upsert_event(
    conn: sqlite3.Connection,
    *,
    raw_snapshot_id: int,
    league_id: int,
    home_team_id: int,
    away_team_id: int,
    event: dict[str, Any],
    updated_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO events (
            external_id,
            raw_snapshot_id,
            league_id,
            home_team_id,
            away_team_id,
            slug,
            status,
            period,
            minute,
            home_score,
            away_score,
            start_time,
            is_editor,
            venue_name,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(external_id) DO UPDATE SET
            raw_snapshot_id = excluded.raw_snapshot_id,
            league_id = excluded.league_id,
            home_team_id = excluded.home_team_id,
            away_team_id = excluded.away_team_id,
            slug = excluded.slug,
            status = excluded.status,
            period = excluded.period,
            minute = excluded.minute,
            home_score = excluded.home_score,
            away_score = excluded.away_score,
            start_time = excluded.start_time,
            is_editor = excluded.is_editor,
            venue_name = excluded.venue_name,
            updated_at = excluded.updated_at
        """,
        (
            int(event["external_id"]),
            raw_snapshot_id,
            league_id,
            home_team_id,
            away_team_id,
            event["slug"],
            event["status"],
            event.get("period"),
            event.get("minute"),
            int(event.get("home_score", 0)),
            int(event.get("away_score", 0)),
            event["start_time"],
            1 if event.get("is_editor") else 0,
            event.get("venue_name"),
            updated_at,
        ),
    )


def fetch_live_events(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            e.external_id AS event_id,
            e.slug,
            e.status,
            e.minute,
            e.period,
            e.is_editor,
            e.start_time,
            e.venue_name,
            e.home_score,
            e.away_score,
            l.external_id AS league_id,
            l.name AS league_name,
            l.country AS league_country,
            l.slug AS league_slug,
            ht.external_id AS home_team_id,
            ht.name AS home_team_name,
            ht.short_name AS home_team_short_name,
            ht.country AS home_team_country,
            at.external_id AS away_team_id,
            at.name AS away_team_name,
            at.short_name AS away_team_short_name,
            at.country AS away_team_country
        FROM events e
        JOIN leagues l ON l.id = e.league_id
        JOIN teams ht ON ht.id = e.home_team_id
        JOIN teams at ON at.id = e.away_team_id
        WHERE e.status = 'LIVE' AND e.is_editor = 0
        ORDER BY e.start_time ASC, e.external_id ASC
        """
    ).fetchall()
    return [row_to_event(row) for row in rows]


def row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["event_id"],
        "slug": row["slug"],
        "status": row["status"],
        "minute": row["minute"],
        "period": row["period"],
        "isEditor": bool(row["is_editor"]),
        "startTime": row["start_time"],
        "league": {
            "id": row["league_id"],
            "name": row["league_name"],
            "country": row["league_country"],
            "slug": row["league_slug"],
        },
        "homeTeam": {
            "id": row["home_team_id"],
            "name": row["home_team_name"],
            "shortName": row["home_team_short_name"],
            "country": row["home_team_country"],
        },
        "awayTeam": {
            "id": row["away_team_id"],
            "name": row["away_team_name"],
            "shortName": row["away_team_short_name"],
            "country": row["away_team_country"],
        },
        "scores": {
            "home": row["home_score"],
            "away": row["away_score"],
        },
        "venueName": row["venue_name"],
    }
