from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ReminderRequest(BaseModel):
    flight_id: str = Field(min_length=1, max_length=64)
    passenger_ids: list[str] = Field(min_length=1, max_length=100)
    channel: Literal["SMS", "BROADCAST", "PHONE"]
    message: str | None = Field(default=None, max_length=500)
    operator_id: str | None = Field(default=None, max_length=64)

    @field_validator("passenger_ids")
    @classmethod
    def unique_passenger_ids(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        return list(dict.fromkeys(cleaned))
