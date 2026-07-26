from __future__ import annotations

import os
from pathlib import Path


TEST_DB = Path(__file__).with_name("test_boarding.sqlite3")
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["DEMO_MODE"] = "true"
os.environ["REMINDER_COOLDOWN_SECONDS"] = "300"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_query_unboarded_and_create_reminder():
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        flights = client.get("/api/flights")
        assert flights.status_code == 200
        flight = flights.json()["items"][0]
        assert flight["checkedInCount"] >= flight["unboardedCount"]

        passengers = client.get(
            f"/api/flights/{flight['id']}/unboarded-passengers"
        )
        assert passengers.status_code == 200
        passenger = passengers.json()["items"][0]

        reminder_payload = {
            "flight_id": flight["id"],
            "passenger_ids": [passenger["passengerId"]],
            "channel": "SMS",
            "message": "Please proceed to the boarding gate.",
            "operator_id": "pytest",
        }
        first = client.post("/api/reminders", json=reminder_payload)
        assert first.status_code == 200
        assert len(first.json()["sent"]) == 1

        duplicate = client.post("/api/reminders", json=reminder_payload)
        assert duplicate.status_code == 200
        assert len(duplicate.json()["sent"]) == 0
        assert "\u51b7\u5374\u65f6\u95f4" in duplicate.json()["skipped"][0]["reason"]

        logs = client.get(f"/api/flights/{flight['id']}/reminders")
        assert logs.status_code == 200
        assert logs.json()["items"][0]["operatorId"] == "pytest"


def teardown_module():
    from app.database import engine

    engine.dispose()
    if TEST_DB.exists():
        TEST_DB.unlink()
