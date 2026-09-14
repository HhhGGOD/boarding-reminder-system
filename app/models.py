from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Flight(Base):
    """航班实例。真实环境应以日期 + 航段对应的唯一 ID 关联。"""

    __tablename__ = "flight"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    flight_no: Mapped[str] = mapped_column(String(16), nullable=False)
    flight_date: Mapped[date] = mapped_column(Date, nullable=False)
    origin: Mapped[str] = mapped_column(String(8), nullable=False)
    destination: Mapped[str] = mapped_column(String(8), nullable=False)
    scheduled_departure: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    boarding_close_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    gate_no: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="BOARDING")

    checkins: Mapped[list["PassengerCheckin"]] = relationship(
        back_populates="flight", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_flight_date_no", "flight_date", "flight_no"),
    )


class PassengerCheckin(Base):
    """旅客值机表。"""

    __tablename__ = "passenger_checkin"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flight_id: Mapped[str] = mapped_column(
        ForeignKey("flight.id"), nullable=False, index=True
    )
    passenger_id: Mapped[str] = mapped_column(String(64), nullable=False)
    passenger_name: Mapped[str] = mapped_column(String(80), nullable=False)
    seat_no: Mapped[str] = mapped_column(String(8), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    passenger_type: Mapped[str] = mapped_column(String(24), default="成人")
    checkin_status: Mapped[str] = mapped_column(String(24), default="CHECKED_IN")
    checked_in_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    flight: Mapped[Flight] = relationship(back_populates="checkins")

    __table_args__ = (
        UniqueConstraint(
            "flight_id", "passenger_id", name="uq_checkin_flight_passenger"
        ),
        Index(
            "idx_checkin_flight_status_passenger",
            "flight_id",
            "checkin_status",
            "passenger_id",
        ),
    )


class PassengerBoarding(Base):
    """旅客当前登机状态表。若真实表为流水表，查询时应先取最新记录。"""

    __tablename__ = "passenger_boarding"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flight_id: Mapped[str] = mapped_column(
        ForeignKey("flight.id"), nullable=False, index=True
    )
    passenger_id: Mapped[str] = mapped_column(String(64), nullable=False)
    boarding_status: Mapped[str] = mapped_column(String(24), default="BOARDED")
    boarded_at: Mapped[datetime | None] = mapped_column(DateTime)
    gate_no: Mapped[str | None] = mapped_column(String(16))

    __table_args__ = (
        UniqueConstraint(
            "flight_id", "passenger_id", name="uq_boarding_flight_passenger"
        ),
        Index(
            "idx_boarding_flight_passenger_status",
            "flight_id",
            "passenger_id",
            "boarding_status",
        ),
    )


class ReminderLog(Base):
    """催促操作审计表。"""

    __tablename__ = "boarding_reminder_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flight_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    passenger_id: Mapped[str] = mapped_column(String(64), nullable=False)
    passenger_name: Mapped[str] = mapped_column(String(80), nullable=False)
    channel: Mapped[str] = mapped_column(String(24), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    operator_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reminded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(128))
    failure_reason: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        Index(
            "idx_reminder_flight_passenger_time",
            "flight_id",
            "passenger_id",
            "reminded_at",
        ),
    )
