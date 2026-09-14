from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

import oracledb

from app.config import settings


class OracleRepositoryError(RuntimeError):
    """A sanitized Oracle access error that is safe to show in the API."""


def _schema_name() -> str:
    schema = settings.oracle_schema.upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9_$#]*", schema):
        raise OracleRepositoryError("Oracle Schema 名称不合法")
    return schema


def _connection() -> oracledb.Connection:
    if not settings.oracle_user or not settings.oracle_password:
        raise OracleRepositoryError("Oracle 用户名或密码尚未配置")
    try:
        return oracledb.connect(
            user=settings.oracle_user,
            password=settings.oracle_password,
            dsn=settings.oracle_dsn,
        )
    except oracledb.Error as exc:
        error = exc.args[0] if exc.args else None
        code = getattr(error, "code", "")
        message = getattr(error, "message", str(exc)).strip()
        prefix = f"ORA-{code}: " if code else ""
        raise OracleRepositoryError(
            f"Oracle 数据库连接失败：{prefix}{message}"
        ) from exc


def _status_binds(
    prefix: str, values: tuple[str, ...], params: dict[str, Any]
) -> str:
    if not values:
        raise OracleRepositoryError(f"状态配置 {prefix} 不能为空")
    placeholders: list[str] = []
    for index, value in enumerate(values):
        name = f"{prefix}_{index}"
        params[name] = value
        placeholders.append(f":{name}")
    return ", ".join(placeholders)


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def ping() -> bool:
    try:
        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("select 1 from dual")
                return cursor.fetchone() == (1,)
    except OracleRepositoryError:
        return False


def list_flights(flight_date: date, flight_no: str | None = None) -> list[dict]:
    schema = _schema_name()
    start_at = datetime.combine(flight_date, datetime.min.time())
    end_at = start_at + timedelta(days=1)
    params: dict[str, Any] = {
        "start_at": start_at,
        "end_at": end_at,
        "flight_no": flight_no.strip().upper() if flight_no else None,
    }
    checked_in = _status_binds(
        "checked_in", settings.oracle_checked_in_statuses, params
    )
    boarded = _status_binds(
        "boarded", settings.oracle_boarded_statuses, params
    )
    sql = f"""
        with flight_scope as (
            select f.FLT_ID, f.FLT_AIRLCODE, f.FLT_NUMBER, f.FLT_SUFFIX,
                   f.FLT_DATE, f.FLT_AIRPORT, f.FLT_DEST, f.FLT_ARVDATE,
                   f.FLT_DWTM, f.FLT_DWSTATUS, f.FLT_TOTALSTAT
              from {schema}.TA_FLIGHT f
             where f.FLT_DATE >= :start_at
               and f.FLT_DATE < :end_at
               and (
                    :flight_no is null
                    or upper(
                        nvl(f.FLT_AIRLCODE, '') ||
                        nvl(f.FLT_NUMBER, '') ||
                        nvl(f.FLT_SUFFIX, '')
                    ) like '%' || :flight_no || '%'
               )
        ),
        boarded_passengers as (
            select distinct s.PSRB_FLTID, s.PSRB_HOSTNBR
              from {schema}.TAB_PSRSTATUS s
              join flight_scope fs on fs.FLT_ID = s.PSRB_FLTID
             where s.PSRB_STATUS in ({boarded})
        ),
        gate_stats as (
            select s.PSRB_FLTID,
                   max(s.PSRB_BRDGATE)
                     keep (dense_rank last order by s.PSRB_TIME) as GATE_NO
              from {schema}.TAB_PSRSTATUS s
              join flight_scope fs on fs.FLT_ID = s.PSRB_FLTID
             where s.PSRB_BRDGATE is not null
             group by s.PSRB_FLTID
        ),
        passenger_stats as (
            select p.SEG_FLTID,
                   count(distinct case
                       when p.PSR_STATUS in ({checked_in})
                       then p.PSR_HOSTNBR end
                   ) as CHECKED_IN_COUNT,
                   count(distinct case
                       when p.PSR_STATUS in ({checked_in})
                        and bp.PSRB_HOSTNBR is not null
                       then p.PSR_HOSTNBR end
                   ) as BOARDED_COUNT
              from {schema}.TA_PSRBASICINFO p
              join flight_scope fs on fs.FLT_ID = p.SEG_FLTID
              left join boarded_passengers bp
                on bp.PSRB_FLTID = p.SEG_FLTID
               and bp.PSRB_HOSTNBR = p.PSR_HOSTNBR
             group by p.SEG_FLTID
        )
        select to_char(fs.FLT_ID) as FLIGHT_ID,
               nvl(fs.FLT_AIRLCODE, '') || nvl(fs.FLT_NUMBER, '') ||
                   nvl(fs.FLT_SUFFIX, '') as FLIGHT_NO,
               fs.FLT_DATE,
               nvl(fs.FLT_AIRPORT, '—') as ORIGIN,
               nvl(fs.FLT_DEST, '—') as DESTINATION,
               fs.FLT_ARVDATE,
               fs.FLT_DWTM,
               nvl(gs.GATE_NO, '—') as GATE_NO,
               nvl(fs.FLT_DWSTATUS, to_char(fs.FLT_TOTALSTAT)) as STATUS,
               nvl(ps.CHECKED_IN_COUNT, 0) as CHECKED_IN_COUNT,
               nvl(ps.BOARDED_COUNT, 0) as BOARDED_COUNT
          from flight_scope fs
          left join passenger_stats ps on ps.SEG_FLTID = fs.FLT_ID
          left join gate_stats gs on gs.PSRB_FLTID = fs.FLT_ID
         order by fs.FLT_DATE, FLIGHT_NO
         fetch first 200 rows only
    """
    try:
        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                results: list[dict] = []
                for row in cursor:
                    checked_count = int(row[9] or 0)
                    boarded_count = int(row[10] or 0)
                    results.append(
                        {
                            "id": row[0],
                            "flightNo": row[1],
                            "flightDate": row[2].date().isoformat(),
                            "origin": row[3],
                            "destination": row[4],
                            "scheduledDeparture": _iso(row[2]),
                            "arrivalTime": _iso(row[5]),
                            "dataUpdatedAt": _iso(row[6]),
                            "boardingCloseAt": None,
                            "gateNo": row[7],
                            "status": row[8] or "—",
                            "checkedInCount": checked_count,
                            "boardedCount": boarded_count,
                            "unboardedCount": max(
                                checked_count - boarded_count, 0
                            ),
                        }
                    )
                return results
    except oracledb.Error as exc:
        raise OracleRepositoryError(f"Oracle 航班查询失败：{exc}") from exc


def get_flight(flight_id: str) -> dict | None:
    schema = _schema_name()
    try:
        numeric_id = int(flight_id)
    except ValueError:
        return None
    sql = f"""
        select to_char(f.FLT_ID),
               nvl(f.FLT_AIRLCODE, '') || nvl(f.FLT_NUMBER, '') ||
                   nvl(f.FLT_SUFFIX, ''),
               f.FLT_DATE, nvl(f.FLT_AIRPORT, '—'), nvl(f.FLT_DEST, '—'),
               nvl((
                   select max(s.PSRB_BRDGATE)
                     keep (dense_rank last order by s.PSRB_TIME)
                     from {schema}.TAB_PSRSTATUS s
                    where s.PSRB_FLTID = f.FLT_ID
                      and s.PSRB_BRDGATE is not null
               ), '—')
          from {schema}.TA_FLIGHT f
         where f.FLT_ID = :flight_id
    """
    try:
        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, flight_id=numeric_id)
                row = cursor.fetchone()
                if not row:
                    return None
                return {
                    "id": row[0],
                    "flightNo": row[1],
                    "flightDate": row[2].date().isoformat(),
                    "origin": row[3],
                    "destination": row[4],
                    "gateNo": row[5],
                }
    except oracledb.Error as exc:
        raise OracleRepositoryError(f"Oracle 航班查询失败：{exc}") from exc


def get_unboarded_passengers(flight_id: str) -> list[dict]:
    schema = _schema_name()
    try:
        numeric_id = int(flight_id)
    except ValueError:
        return []
    params: dict[str, Any] = {"flight_id": numeric_id}
    checked_in = _status_binds(
        "checked_in", settings.oracle_checked_in_statuses, params
    )
    boarded = _status_binds(
        "boarded", settings.oracle_boarded_statuses, params
    )
    sql = f"""
        with current_passengers as (
            select p.*,
                   row_number() over (
                       partition by p.SEG_FLTID, p.PSR_HOSTNBR
                       order by p.PSR_CKITIME desc nulls last
                   ) as RN
              from {schema}.TA_PSRBASICINFO p
             where p.SEG_FLTID = :flight_id
               and p.PSR_STATUS in ({checked_in})
        )
        select to_char(p.PSR_HOSTNBR) as PASSENGER_ID,
               nvl(p.PSR_CHNNAME, nvl(p.PSR_NAME, '未命名旅客')) as PASSENGER_NAME,
               nvl(p.PSR_SEG_SEATNBR, nvl(p.PSR_SEATNBR, '—')) as SEAT_NO,
               nvl(p.PSR_CLASS, '普通') as PASSENGER_TYPE,
               p.PSR_CKITIME
          from current_passengers p
         where p.RN = 1
           and not exists (
               select 1
                 from {schema}.TAB_PSRSTATUS s
                where s.PSRB_FLTID = p.SEG_FLTID
                  and s.PSRB_HOSTNBR = p.PSR_HOSTNBR
                  and s.PSRB_STATUS in ({boarded})
           )
         order by p.PSR_SEG_SEATNBR nulls last, p.PSR_SEATNBR nulls last
    """
    try:
        with _connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                return [
                    {
                        "passengerId": row[0],
                        "passengerName": row[1],
                        "seatNo": row[2],
                        "phoneMasked": "—",
                        "passengerType": row[3],
                        "checkedInAt": _iso(row[4]),
                        "lastReminderAt": None,
                        "lastReminderChannel": None,
                        "lastReminderStatus": None,
                    }
                    for row in cursor
                ]
    except oracledb.Error as exc:
        raise OracleRepositoryError(f"Oracle 旅客查询失败：{exc}") from exc
