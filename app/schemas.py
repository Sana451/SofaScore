from __future__ import annotations

from pydantic import BaseModel


class ScoreOut(BaseModel):
    home: int
    away: int


class TeamOut(BaseModel):
    id: int
    name: str
    shortName: str | None = None
    country: str | None = None


class LeagueOut(BaseModel):
    id: int
    name: str
    country: str | None = None
    slug: str | None = None


class EventOut(BaseModel):
    id: int
    slug: str
    status: str
    minute: int | None = None
    period: str | None = None
    isEditor: bool
    startTime: str
    league: LeagueOut
    homeTeam: TeamOut
    awayTeam: TeamOut
    scores: ScoreOut
    venueName: str | None = None


class LiveEventsResponse(BaseModel):
    events: list[EventOut]
