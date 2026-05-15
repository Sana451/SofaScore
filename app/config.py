from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = BASE_DIR / "data" / "sofascore.db"
DEFAULT_FIXTURE_PATH = BASE_DIR / "fixtures" / "live_payload.json"


@dataclass(frozen=True)
class Settings:
    db_path: Path = DEFAULT_DB_PATH
    fixture_path: Path = DEFAULT_FIXTURE_PATH
    auto_seed: bool = True


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return True
    return value.strip().lower() not in {"0", "false", "no", "off"}


def get_settings() -> Settings:
    return Settings(
        db_path=Path(os.getenv("SOFASCORE_DB_PATH", DEFAULT_DB_PATH)),
        fixture_path=Path(os.getenv("SOFASCORE_FIXTURE_PATH", DEFAULT_FIXTURE_PATH)),
        auto_seed=_is_truthy(os.getenv("SOFASCORE_AUTO_SEED")),
    )
