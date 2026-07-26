from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Flight, PassengerBoarding, PassengerCheckin


DEMO_PASSENGERS = [
    ("P001", "张伟", "12A", "13800138001", "成人"),
    ("P002", "李娜", "12B", "13900139002", "成人"),
    ("P003", "王强", "18F", "13600136003", "成人"),
    ("P004", "陈晨", "21C", "13500135004", "成人"),
    ("P005", "刘洋", "07A", "13700137005", "金卡"),
    ("P006", "赵敏", "07C", "13300133006", "成人"),
    ("P007", "周杰", "29D", "13200132007", "成人"),
    ("P008", "吴芳", "29E", "13100131008", "携童"),
]


def seed_demo_data(db: Session) -> None:
    if db.scalar(select(Flight.id).limit(1)):
        return

    today = date.today()
    flights = [
        Flight(
            id=f"{today.isoformat()}-MU5101-SHA-PEK",
            flight_no="MU5101",
            flight_date=today,
            origin="SHA",
            destination="PEK",
            scheduled_departure=datetime.combine(today, time(14, 30)),
            boarding_close_at=datetime.combine(today, time(14, 10)),
            gate_no="C37",
            status="BOARDING",
        ),
        Flight(
            id=f"{today.isoformat()}-CA1888-SHA-CAN",
            flight_no="CA1888",
            flight_date=today,
            origin="SHA",
            destination="CAN",
            scheduled_departure=datetime.combine(today, time(16, 5)),
            boarding_close_at=datetime.combine(today, time(15, 45)),
            gate_no="B12",
            status="CHECK_IN",
        ),
        Flight(
            id=f"{today.isoformat()}-CZ6502-SHA-SZX",
            flight_no="CZ6502",
            flight_date=today,
            origin="SHA",
            destination="SZX",
            scheduled_departure=datetime.combine(today, time(18, 20)),
            boarding_close_at=datetime.combine(today, time(18, 0)),
            gate_no="D08",
            status="CHECK_IN",
        ),
    ]
    db.add_all(flights)

    now = datetime.now().replace(microsecond=0)
    for index, (passenger_id, name, seat, phone, passenger_type) in enumerate(
        DEMO_PASSENGERS
    ):
        db.add(
            PassengerCheckin(
                flight_id=flights[0].id,
                passenger_id=passenger_id,
                passenger_name=name,
                seat_no=seat,
                phone=phone,
                passenger_type=passenger_type,
                checkin_status="CHECKED_IN",
                checked_in_at=now - timedelta(minutes=70 - index * 4),
            )
        )

    for passenger_id in ("P001", "P003", "P006"):
        db.add(
            PassengerBoarding(
                flight_id=flights[0].id,
                passenger_id=passenger_id,
                boarding_status="BOARDED",
                boarded_at=now - timedelta(minutes=8),
                gate_no=flights[0].gate_no,
            )
        )

    for flight_index, flight in enumerate(flights[1:], start=1):
        for index in range(5):
            passenger_no = flight_index * 100 + index
            passenger_id = f"P{passenger_no}"
            db.add(
                PassengerCheckin(
                    flight_id=flight.id,
                    passenger_id=passenger_id,
                    passenger_name=["孙悦", "马超", "高远", "林青", "郑宇"][index],
                    seat_no=f"{10 + index}{'ABCDF'[index]}",
                    phone=f"1380000{passenger_no:04d}",
                    passenger_type="成人",
                    checkin_status="CHECKED_IN",
                    checked_in_at=now - timedelta(minutes=45 - index * 3),
                )
            )
        db.add(
            PassengerBoarding(
                flight_id=flight.id,
                passenger_id=f"P{flight_index * 100}",
                boarding_status="BOARDED",
                boarded_at=now - timedelta(minutes=5),
                gate_no=flight.gate_no,
            )
        )

    db.commit()
