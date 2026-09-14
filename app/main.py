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
from app.oracle_repository import OracleRepositoryError, ping as oracle_ping
from app.schemas import ReminderRequest
from app.seed import seed_demo_data
from app.service import (
    create_reminders_for_source,
    flight_exists_for_source,
    get_reminder_logs,
    get_unboarded_for_source,
    list_flights_for_source,
)


APP_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Only the local SQLite audit/demo database is created here. Oracle is read-only.
    Base.metadata.create_all(bind=engine)
    if not settings.is_oracle:
        with SessionLocal() as db:
            seed_demo_data(db)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.2.0-demo2",
    description="联查 Oracle 航班、值机与登机状态，并记录催促操作。",
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
            "data_source": settings.data_source,
        },
    )


@app.get("/api/health")
def health():
    database_connected = oracle_ping() if settings.is_oracle else True
    return {
        "status": "ok" if database_connected else "degraded",
        "demoMode": settings.demo_mode,
        "dataSource": settings.data_source,
        "databaseConnected": database_connected,
    }


@app.get("/api/config")
def config():
    return {
        "appName": settings.app_name,
        "demoMode": settings.demo_mode,
        "dataSource": settings.data_source,
        "reminderCooldownSeconds": settings.reminder_cooldown_seconds,
        "defaultOperator": settings.default_operator,
    }


@app.get("/api/flights")
def flights(
    flight_date: date = Query(default_factory=date.today, alias="date"),
    flight_no: str = Query(min_length=1, max_length=16),
    db: Session = Depends(get_db),
):
    normalized_flight_no = flight_no.strip().upper()
    if not normalized_flight_no:
        raise HTTPException(status_code=422, detail="请输入航班号后再查询")
    try:
        return {"items": list_flights_for_source(db, flight_date, normalized_flight_no)}
    except OracleRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/flights/{flight_id}/unboarded-passengers")
def unboarded_passengers(
    flight_id: str,
    db: Session = Depends(get_db),
):
    try:
        if not flight_exists_for_source(db, flight_id):
            raise HTTPException(status_code=404, detail="航班不存在")
        return {"items": get_unboarded_for_source(db, flight_id)}
    except OracleRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/flights/{flight_id}/reminders")
def reminder_logs(
    flight_id: str,
    db: Session = Depends(get_db),
):
    try:
        if not flight_exists_for_source(db, flight_id):
            raise HTTPException(status_code=404, detail="航班不存在")
        return {"items": get_reminder_logs(db, flight_id)}
    except OracleRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/reminders")
def remind(
    payload: ReminderRequest,
    db: Session = Depends(get_db),
):
    try:
        result = create_reminders_for_source(
            db=db,
            flight_id=payload.flight_id,
            passenger_ids=payload.passenger_ids,
            channel=payload.channel,
            message=payload.message,
            operator_id=payload.operator_id or settings.default_operator,
        )
    ###LCTM
    except OracleRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not result["sent"] and result["skipped"] == [{"reason": "航班不存在"}]:
        raise HTTPException(status_code=404, detail="航班不存在")
    return result
