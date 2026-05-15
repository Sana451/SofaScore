from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

FOOTBALL_DATA_LIVE_PATH = "/v4/matches"
LIVE_STATUSES = {"IN_PLAY", "PAUSED"}


def build_live_matches_url(base_url: str, competitions: str | None = None) -> str:
    query: dict[str, str] = {"status": "LIVE"}
    if competitions:
        query["competitions"] = competitions
    return f"{base_url.rstrip('/')}{FOOTBALL_DATA_LIVE_PATH}?{urlencode(query)}"


def normalize_football_data_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    matches = payload.get("matches") or []
    return [normalize_match(match) for match in matches if isinstance(match, dict)]


def normalize_match(match: dict[str, Any]) -> dict[str, Any]:
    competition = match.get("competition") or {}
    area = competition.get("area") or {}
    home_team = match.get("homeTeam") or {}
    away_team = match.get("awayTeam") or {}
    score = match.get("score") or {}

    status = str(match.get("status") or "SCHEDULED").upper()
    normalized_status = map_status(status)
    start_time = str(match.get("utcDate") or match.get("startTime") or "")

    return {
        "external_id": int(match["id"]),
        "slug": build_slug(match, competition, home_team, away_team),
        "status": normalized_status,
        "period": map_period(status),
        "minute": extract_minute(match),
        "home_score": extract_score(score, side="home"),
        "away_score": extract_score(score, side="away"),
        "start_time": start_time,
        "is_editor": False,
        "venue_name": extract_venue_name(match),
        "league": {
            "id": int(competition.get("id") or 0),
            "name": str(competition.get("name") or "Unknown competition"),
            "country": area.get("name"),
            "slug": competition.get("code") or competition.get("name"),
        },
        "home_team": {
            "id": int(home_team.get("id") or 0),
            "name": str(home_team.get("name") or "Unknown home team"),
            "short_name": home_team.get("tla") or home_team.get("shortName"),
            "country": home_team.get("country"),
        },
        "away_team": {
            "id": int(away_team.get("id") or 0),
            "name": str(away_team.get("name") or "Unknown away team"),
            "short_name": away_team.get("tla") or away_team.get("shortName"),
            "country": away_team.get("country"),
        },
    }


def build_slug(
    match: dict[str, Any],
    competition: dict[str, Any],
    home_team: dict[str, Any],
    away_team: dict[str, Any],
) -> str:
    explicit_slug = match.get("slug")
    if isinstance(explicit_slug, str) and explicit_slug.strip():
        return explicit_slug

    parts = [
        competition.get("code") or competition.get("name") or "competition",
        home_team.get("shortName") or home_team.get("tla") or home_team.get("name") or "home",
        away_team.get("shortName") or away_team.get("tla") or away_team.get("name") or "away",
        str(match.get("id")),
    ]
    return "-".join(_slugify(part) for part in parts if part)


def map_status(status: str) -> str:
    if status in LIVE_STATUSES:
        return "LIVE"
    if status in {"TIMED", "SCHEDULED"}:
        return "SCHEDULED"
    if status in {"FINISHED", "POSTPONED", "SUSPENDED", "CANCELLED"}:
        return status
    return status


def map_period(status: str) -> str | None:
    if status == "IN_PLAY":
        return "1H"
    if status == "PAUSED":
        return "HT"
    if status == "FINISHED":
        return "FT"
    return None


def extract_minute(match: dict[str, Any]) -> int | None:
    minute = match.get("minute")
    if isinstance(minute, int):
        return minute
    if isinstance(minute, str) and minute.isdigit():
        return int(minute)
    return None


def extract_venue_name(match: dict[str, Any]) -> str | None:
    venue = match.get("venue") or {}
    if isinstance(venue, dict):
        name = venue.get("name")
        if isinstance(name, str):
            return name
    venue_name = match.get("venueName")
    return venue_name if isinstance(venue_name, str) else None


def extract_score(score: dict[str, Any], *, side: str) -> int:
    candidates = [
        score.get("current"),
        score.get("fullTime"),
        score.get("halfTime"),
        score.get("regularTime"),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            value = candidate.get(side)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
    return 0


def _slugify(value: Any) -> str:
    text = str(value).strip().lower()
    characters: list[str] = []
    previous_was_dash = False
    for char in text:
        if char.isalnum():
            characters.append(char)
            previous_was_dash = False
        elif char in {" ", "-", "_", "/", "."} and not previous_was_dash:
            characters.append("-")
            previous_was_dash = True
    slug = "".join(characters).strip("-")
    return slug or "event"
