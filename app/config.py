from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env.local", override=False)


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_csv(value: str | None, default: str) -> tuple[str, ...]:
    raw = value if value is not None else default
    return tuple(item.strip().upper() for item in raw.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "登机协同台")
    data_source: str = os.getenv("DATA_SOURCE", "sqlite").strip().lower()
    database_url: str = os.getenv(
        "DATABASE_URL", "sqlite:///./boarding_reminder.sqlite3"
    )
    demo_mode: bool = _as_bool(os.getenv("DEMO_MODE"), default=True)
    reminder_cooldown_seconds: int = int(
        os.getenv("REMINDER_COOLDOWN_SECONDS", "300")
    )
    default_operator: str = os.getenv("DEFAULT_OPERATOR", "值机保障-演示账号")
    oracle_host: str = os.getenv("ORACLE_HOST", "127.0.0.1")
    oracle_port: int = int(os.getenv("ORACLE_PORT", "1521"))
    oracle_service_name: str = os.getenv("ORACLE_SERVICE_NAME", "FREEPDB1")
    oracle_user: str = os.getenv("ORACLE_USER", "")
    oracle_password: str = os.getenv("ORACLE_PASSWORD", "")
    oracle_schema: str = os.getenv("ORACLE_SCHEMA", "DCS_SYS").upper()
    oracle_checked_in_statuses: tuple[str, ...] = _as_csv(
        os.getenv("ORACLE_CHECKED_IN_STATUSES"), "AC"
    )
    oracle_boarded_statuses: tuple[str, ...] = _as_csv(
        os.getenv("ORACLE_BOARDED_STATUSES"), "BD"
    )

    @property
    def is_oracle(self) -> bool:
        return self.data_source == "oracle"

    @property
    def oracle_dsn(self) -> str:
        return (
            f"{self.oracle_host}:{self.oracle_port}/{self.oracle_service_name}"
        )


settings = Settings()
