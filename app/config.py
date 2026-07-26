from __future__ import annotations

import os
from dataclasses import dataclass


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "登机协同台")
    database_url: str = os.getenv(
        "DATABASE_URL", "sqlite:///./boarding_reminder.sqlite3"
    )
    demo_mode: bool = _as_bool(os.getenv("DEMO_MODE"), default=True)
    reminder_cooldown_seconds: int = int(
        os.getenv("REMINDER_COOLDOWN_SECONDS", "300")
    )
    default_operator: str = os.getenv("DEFAULT_OPERATOR", "值机保障-演示账号")


settings = Settings()
