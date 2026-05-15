PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS raw_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS leagues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL,
    country TEXT,
    slug TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL,
    short_name TEXT,
    country TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id INTEGER NOT NULL UNIQUE,
    raw_snapshot_id INTEGER NOT NULL,
    league_id INTEGER NOT NULL,
    home_team_id INTEGER NOT NULL,
    away_team_id INTEGER NOT NULL,
    slug TEXT NOT NULL,
    status TEXT NOT NULL,
    period TEXT,
    minute INTEGER,
    home_score INTEGER NOT NULL DEFAULT 0,
    away_score INTEGER NOT NULL DEFAULT 0,
    start_time TEXT NOT NULL,
    is_editor INTEGER NOT NULL DEFAULT 0 CHECK (is_editor IN (0, 1)),
    venue_name TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (raw_snapshot_id) REFERENCES raw_snapshots (id) ON DELETE CASCADE,
    FOREIGN KEY (league_id) REFERENCES leagues (id) ON DELETE RESTRICT,
    FOREIGN KEY (home_team_id) REFERENCES teams (id) ON DELETE RESTRICT,
    FOREIGN KEY (away_team_id) REFERENCES teams (id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_events_public_live
    ON events (is_editor, status, start_time);
CREATE INDEX IF NOT EXISTS idx_events_league_status
    ON events (league_id, status, start_time);
CREATE INDEX IF NOT EXISTS idx_events_home_team
    ON events (home_team_id);
CREATE INDEX IF NOT EXISTS idx_events_away_team
    ON events (away_team_id);
