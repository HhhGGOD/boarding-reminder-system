from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Flight, PassengerBoarding, PassengerCheckin, ReminderLog
from app import oracle_repository


ACTIVE_FLIGHT_STATUSES = ("CHECK_IN", "BOARDING", "FINAL_CALL", "DELAYED")


def mask_phone(phone: str | None) -> str:
    if not phone:
        return "—"
    if len(phone) < 7:
        return "*" * len(phone)
    return f"{phone[:3]}****{phone[-4:]}"


def list_flights(
    db: Session, flight_date: date, flight_no: str | None = None
) -> list[dict]:
    filters = [
        Flight.flight_date == flight_date,
        Flight.status.in_(ACTIVE_FLIGHT_STATUSES),
    ]
    if flight_no:
        filters.append(Flight.flight_no.ilike(f"%{flight_no.strip()}%"))

    flights = db.scalars(
        select(Flight)
        .where(*filters)
        .order_by(Flight.scheduled_departure)
    ).all()

    results: list[dict] = []
    for flight in flights:
        checked_in_count = db.scalar(
            select(func.count(PassengerCheckin.id)).where(
                PassengerCheckin.flight_id == flight.id,
                PassengerCheckin.checkin_status == "CHECKED_IN",
            )
        ) or 0
        boarded_count = db.scalar(
            select(func.count(PassengerBoarding.id)).where(
                PassengerBoarding.flight_id == flight.id,
                PassengerBoarding.boarding_status == "BOARDED",
            )
        ) or 0
        results.append(
            {
                "id": flight.id,
                "flightNo": flight.flight_no,
                "flightDate": flight.flight_date.isoformat(),
                "origin": flight.origin,
                "destination": flight.destination,
                "scheduledDeparture": flight.scheduled_departure.isoformat(),
                "boardingCloseAt": flight.boarding_close_at.isoformat(),
                "gateNo": flight.gate_no,
                "status": flight.status,
                "checkedInCount": checked_in_count,
                "boardedCount": boarded_count,
                "unboardedCount": max(checked_in_count - boarded_count, 0),
            }
        )
    return results


def _unboarded_statement(flight_id: str):
    return (
        select(PassengerCheckin)
        .outerjoin(
            PassengerBoarding,
            and_(
                PassengerBoarding.flight_id == PassengerCheckin.flight_id,
                PassengerBoarding.passenger_id == PassengerCheckin.passenger_id,
            ),
        )
        .where(
            PassengerCheckin.flight_id == flight_id,
            PassengerCheckin.checkin_status == "CHECKED_IN",
            or_(
                PassengerBoarding.id.is_(None),
                PassengerBoarding.boarding_status != "BOARDED",
            ),
        )
        .order_by(PassengerCheckin.seat_no)
    )


def get_unboarded_passengers(db: Session, flight_id: str) -> list[dict]:
    passengers = db.scalars(_unboarded_statement(flight_id)).all()
    results: list[dict] = []
    for passenger in passengers:
        latest = db.scalar(
            select(ReminderLog)
            .where(
                ReminderLog.flight_id == flight_id,
                ReminderLog.passenger_id == passenger.passenger_id,
            )
            .order_by(ReminderLog.reminded_at.desc())
            .limit(1)
        )
        results.append(
            {
                "passengerId": passenger.passenger_id,
                "passengerName": passenger.passenger_name,
                "seatNo": passenger.seat_no,
                "phoneMasked": mask_phone(passenger.phone),
                "passengerType": passenger.passenger_type,
                "checkedInAt": passenger.checked_in_at.isoformat(),
                "lastReminderAt": latest.reminded_at.isoformat() if latest else None,
                "lastReminderChannel": latest.channel if latest else None,
                "lastReminderStatus": latest.status if latest else None,
            }
        )
    return results


def get_reminder_logs(db: Session, flight_id: str) -> list[dict]:
    logs = db.scalars(
        select(ReminderLog)
        .where(ReminderLog.flight_id == flight_id)
        .order_by(ReminderLog.reminded_at.desc())
        .limit(200)
    ).all()
    return [
        {
            "id": log.id,
            "passengerId": log.passenger_id,
            "passengerName": log.passenger_name,
            "channel": log.channel,
            "message": log.message,
            "operatorId": log.operator_id,
            "remindedAt": log.reminded_at.isoformat(),
            "status": log.status,
        }
        for log in logs
    ]


def create_reminders(
    db: Session,
    flight_id: str,
    passenger_ids: list[str],
    channel: str,
    message: str | None,
    operator_id: str,
) -> dict:
    flight = db.get(Flight, flight_id)
    if not flight:
        return {"sent": [], "skipped": [{"reason": "航班不存在"}]}

    now = datetime.now().replace(microsecond=0)
    cooldown_after = now - timedelta(seconds=settings.reminder_cooldown_seconds)
    current_unboarded = {
        passenger.passenger_id: passenger
        for passenger in db.scalars(_unboarded_statement(flight_id)).all()
    }

    default_message = (
        f"温馨提示：您乘坐的 {flight.flight_no} 航班即将结束登机，"
        f"请尽快前往 {flight.gate_no} 登机口。"
    )
    final_message = (message or default_message).strip()
    sent: list[dict] = []
    skipped: list[dict] = []

    for passenger_id in passenger_ids:
        passenger = current_unboarded.get(passenger_id)
        if not passenger:
            skipped.append(
                {"passengerId": passenger_id, "reason": "旅客已登机或不在当前航班"}
            )
            continue

        recent = db.scalar(
            select(ReminderLog)
            .where(
                ReminderLog.flight_id == flight_id,
                ReminderLog.passenger_id == passenger_id,
                ReminderLog.reminded_at >= cooldown_after,
            )
            .order_by(ReminderLog.reminded_at.desc())
            .limit(1)
        )
        if recent:
            skipped.append(
                {
                    "passengerId": passenger_id,
                    "passengerName": passenger.passenger_name,
                    "reason": "冷却时间内已催促，请勿重复发送",
                }
            )
            continue

        status = "SIMULATED" if settings.demo_mode else "QUEUED"
        provider_message_id = f"demo-{uuid4()}" if settings.demo_mode else None
        log = ReminderLog(
            flight_id=flight_id,
            passenger_id=passenger_id,
            passenger_name=passenger.passenger_name,
            channel=channel,
            message=final_message,
            operator_id=operator_id,
            reminded_at=now,
            status=status,
            provider_message_id=provider_message_id,
        )
        db.add(log)
        sent.append(
            {
                "passengerId": passenger_id,
                "passengerName": passenger.passenger_name,
                "status": status,
            }
        )

    db.commit()
    return {"sent": sent, "skipped": skipped}


def list_flights_for_source(
    db: Session, flight_date: date, flight_no: str | None = None
) -> list[dict]:
    if settings.is_oracle:
        return oracle_repository.list_flights(flight_date, flight_no)
    return list_flights(db, flight_date, flight_no)


def flight_exists_for_source(db: Session, flight_id: str) -> bool:
    if settings.is_oracle:
        return oracle_repository.get_flight(flight_id) is not None
    return db.get(Flight, flight_id) is not None


def get_unboarded_for_source(db: Session, flight_id: str) -> list[dict]:
    if not settings.is_oracle:
        return get_unboarded_passengers(db, flight_id)

    passengers = oracle_repository.get_unboarded_passengers(flight_id)
    for passenger in passengers:
        latest = db.scalar(
            select(ReminderLog)
            .where(
                ReminderLog.flight_id == flight_id,
                ReminderLog.passenger_id == passenger["passengerId"],
            )
            .order_by(ReminderLog.reminded_at.desc())
            .limit(1)
        )
        if latest:
            passenger["lastReminderAt"] = latest.reminded_at.isoformat()
            passenger["lastReminderChannel"] = latest.channel
            passenger["lastReminderStatus"] = latest.status
    return passengers


def create_reminders_for_source(
    db: Session,
    flight_id: str,
    passenger_ids: list[str],
    channel: str,
    message: str | None,
    operator_id: str,
) -> dict:
    if not settings.is_oracle:
        return create_reminders(
            db, flight_id, passenger_ids, channel, message, operator_id
        )

    flight = oracle_repository.get_flight(flight_id)
    if not flight:
        return {"sent": [], "skipped": [{"reason": "航班不存在"}]}

    now = datetime.now().replace(microsecond=0)
    cooldown_after = now - timedelta(seconds=settings.reminder_cooldown_seconds)
    current_unboarded = {
        passenger["passengerId"]: passenger
        for passenger in oracle_repository.get_unboarded_passengers(flight_id)
    }
    default_message = (
        f"温馨提示：您乘坐的 {flight['flightNo']} 航班即将结束登机，"
        f"请尽快前往 {flight['gateNo']} 登机口。"
    )
    final_message = (message or default_message).strip()
    sent: list[dict] = []
    skipped: list[dict] = []

    for passenger_id in passenger_ids:
        passenger = current_unboarded.get(passenger_id)
        if not passenger:
            skipped.append(
                {
                    "passengerId": passenger_id,
                    "reason": "旅客已登机或不在当前航班",
                }
            )
            continue
        recent = db.scalar(
            select(ReminderLog)
            .where(
                ReminderLog.flight_id == flight_id,
                ReminderLog.passenger_id == passenger_id,
                ReminderLog.reminded_at >= cooldown_after,
            )
            .order_by(ReminderLog.reminded_at.desc())
            .limit(1)
        )
        if recent:
            skipped.append(
                {
                    "passengerId": passenger_id,
                    "passengerName": passenger["passengerName"],
                    "reason": "冷却时间内已催促，请勿重复发送",
                }
            )
            continue
        status = "SIMULATED" if settings.demo_mode else "QUEUED"
        db.add(
            ReminderLog(
                flight_id=flight_id,
                passenger_id=passenger_id,
                passenger_name=passenger["passengerName"],
                channel=channel,
                message=final_message,
                operator_id=operator_id,
                reminded_at=now,
                status=status,
                provider_message_id=(
                    f"demo-{uuid4()}" if settings.demo_mode else None
                ),
            )
        )
        sent.append(
            {
                "passengerId": passenger_id,
                "passengerName": passenger["passengerName"],
                "status": status,
            }
        )
    db.commit()
    return {"sent": sent, "skipped": skipped}
