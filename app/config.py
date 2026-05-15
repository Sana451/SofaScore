from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = BASE_DIR / "data" / "sofascore.db"
DEFAULT_FIXTURE_PATH = BASE_DIR / "fixtures" / "live_payload.json"


@dataclass(frozen=True)
class Settings:
    db_path: Path = DEFAULT_DB_PATH
    fixture_path: Path = DEFAULT_FIXTURE_PATH
    auto_seed: bool = True
    log_level: str = "INFO"
    football_data_token: str | None = None
    football_data_base_url: str = "https://api.football-data.org"
    football_data_competitions: str | None = None
    football_data_poll_interval_seconds: int = 30
    football_data_timeout_seconds: float = 10.0

    @property
    def polling_enabled(self) -> bool:
        return bool(self.football_data_token)

    @property
    def should_seed_fixture(self) -> bool:
        return self.auto_seed and not self.polling_enabled

    @property
    def runtime_mode(self) -> str:
        return "polling" if self.polling_enabled else "fixture"


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return True
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _optional_str(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def load_environment() -> None:
    load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)


def get_settings() -> Settings:
    load_environment()
    return Settings(
        db_path=Path(os.getenv("SOFASCORE_DB_PATH", DEFAULT_DB_PATH)),
        fixture_path=Path(os.getenv("SOFASCORE_FIXTURE_PATH", DEFAULT_FIXTURE_PATH)),
        auto_seed=_is_truthy(os.getenv("SOFASCORE_AUTO_SEED")),
        log_level=os.getenv("SOFASCORE_LOG_LEVEL", "INFO").strip() or "INFO",
        football_data_token=_optional_str(os.getenv("SOFASCORE_FOOTBALL_DATA_TOKEN")),
        football_data_base_url=os.getenv(
            "SOFASCORE_FOOTBALL_DATA_BASE_URL", "https://api.football-data.org"
        ),
        football_data_competitions=_optional_str(os.getenv("SOFASCORE_FOOTBALL_DATA_COMPETITIONS")),
        football_data_poll_interval_seconds=int(
            os.getenv("SOFASCORE_FOOTBALL_DATA_POLL_INTERVAL_SECONDS", "30")
        ),
        football_data_timeout_seconds=float(
            os.getenv("SOFASCORE_FOOTBALL_DATA_TIMEOUT_SECONDS", "10.0")
        ),
    )
