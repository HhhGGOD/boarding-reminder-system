from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, SessionLocal, engine, get_db
from app.models import Flight
from app.schemas import ReminderRequest
from app.seed import seed_demo_data
from app.service import (
    create_reminders,
    get_reminder_logs,
    get_unboarded_passengers,
    list_flights,
)


APP_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="查询已值机但未登机旅客，并记录催促操作。",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": settings.app_name,
            "demo_mode": settings.demo_mode,
        },
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "demoMode": settings.demo_mode}


@app.get("/api/config")
def config():
    return {
        "appName": settings.app_name,
        "demoMode": settings.demo_mode,
        "reminderCooldownSeconds": settings.reminder_cooldown_seconds,
        "defaultOperator": settings.default_operator,
    }


@app.get("/api/flights")
def flights(
    flight_date: date = Query(default_factory=date.today, alias="date"),
    flight_no: str | None = Query(default=None, max_length=16),
    db: Session = Depends(get_db),
):
    return {"items": list_flights(db, flight_date, flight_no)}


@app.get("/api/flights/{flight_id}/unboarded-passengers")
def unboarded_passengers(
    flight_id: str,
    db: Session = Depends(get_db),
):
    if not db.get(Flight, flight_id):
        raise HTTPException(status_code=404, detail="航班不存在")
    return {"items": get_unboarded_passengers(db, flight_id)}


@app.get("/api/flights/{flight_id}/reminders")
def reminder_logs(
    flight_id: str,
    db: Session = Depends(get_db),
):
    if not db.get(Flight, flight_id):
        raise HTTPException(status_code=404, detail="航班不存在")
    return {"items": get_reminder_logs(db, flight_id)}


@app.post("/api/reminders")
def remind(
    payload: ReminderRequest,
    db: Session = Depends(get_db),
):
    result = create_reminders(
        db=db,
        flight_id=payload.flight_id,
        passenger_ids=payload.passenger_ids,
        channel=payload.channel,
        message=payload.message,
        operator_id=payload.operator_id or settings.default_operator,
    )
    if not result["sent"] and result["skipped"] == [{"reason": "航班不存在"}]:
        raise HTTPException(status_code=404, detail="航班不存在")
    return result
