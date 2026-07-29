"""Structured patient / appointment lookups and gated write path."""

from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from clinic_mcp import db
from clinic_mcp.errors import (
    CODE_INVALID_DATE_RANGE,
    CODE_INVALID_DATETIME,
    CODE_PATIENT_NOT_FOUND,
    ClinicToolError,
)
from clinic_mcp.schemas import (
    AppointmentRequest,
    AppointmentStatus,
    AppointmentSummary,
    CreateAppointmentResult,
    GetPatientRecordResult,
    ListAppointmentsResult,
    PatientRecord,
    RequestStatus,
)

load_dotenv()

CLINIC_TZ = ZoneInfo(os.environ.get("CLINIC_TZ", "America/Los_Angeles"))


def _ensure_aware(dt: datetime) -> datetime:
    """Naive datetimes are interpreted in the clinic timezone."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=CLINIC_TZ)
    return dt


def _row_to_appointment(row: dict, *, patient_name: str | None = None) -> AppointmentSummary:
    return AppointmentSummary(
        appointment_id=int(row["id"]),
        patient_id=row["patient_id"],
        patient_name=patient_name or row.get("full_name"),
        starts_at=row["starts_at"],
        service=row["service"],
        status=AppointmentStatus(row["status"]),
    )


def get_patient(patient_id: str) -> dict:
    row = db.fetchone(
        """
        SELECT patient_id, full_name, email, phone, insurance, last_visit
        FROM patients
        WHERE patient_id = %s
        """,
        (patient_id,),
    )
    if row is None:
        raise ClinicToolError(
            CODE_PATIENT_NOT_FOUND,
            f"No patient found with id {patient_id!r}. "
            "Known demo ids include 'jordan-lee', 'maria-vargas', 'sam-okonkwo', 'ava-chen'.",
            details={"patient_id": patient_id},
        )
    return row


def next_confirmed_appointment(patient_id: str) -> AppointmentSummary | None:
    row = db.fetchone(
        """
        SELECT id, patient_id, starts_at, service, status
        FROM appointments
        WHERE patient_id = %s
          AND status = 'confirmed'
          AND starts_at >= now()
        ORDER BY starts_at ASC
        LIMIT 1
        """,
        (patient_id,),
    )
    if row is None:
        return None
    return _row_to_appointment(row)


def get_patient_record(patient_id: str) -> GetPatientRecordResult:
    patient = get_patient(patient_id)
    upcoming = next_confirmed_appointment(patient_id)
    if upcoming is not None:
        upcoming = upcoming.model_copy(update={"patient_name": patient["full_name"]})
    return GetPatientRecordResult(
        patient=PatientRecord(
            patient_id=patient["patient_id"],
            full_name=patient["full_name"],
            email=patient["email"],
            phone=patient["phone"],
            insurance=patient["insurance"],
            last_visit=patient["last_visit"],
            upcoming_appointment=upcoming,
        )
    )


def list_appointments(date_from: date, date_to: date) -> ListAppointmentsResult:
    if date_to < date_from:
        raise ClinicToolError(
            CODE_INVALID_DATE_RANGE,
            "date_to must be on or after date_from",
            details={"date_from": str(date_from), "date_to": str(date_to)},
        )

    start = datetime.combine(date_from, time.min, tzinfo=CLINIC_TZ)
    # Inclusive end-of-day in clinic timezone
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=CLINIC_TZ)

    rows = db.fetchall(
        """
        SELECT a.id, a.patient_id, a.starts_at, a.service, a.status, p.full_name
        FROM appointments a
        JOIN patients p ON p.patient_id = a.patient_id
        WHERE a.status = 'confirmed'
          AND a.starts_at >= %s
          AND a.starts_at < %s
        ORDER BY a.starts_at ASC
        """,
        (start, end),
    )
    appointments = [_row_to_appointment(r) for r in rows]
    return ListAppointmentsResult(
        date_from=date_from,
        date_to=date_to,
        count=len(appointments),
        appointments=appointments,
    )


def create_appointment_request(
    patient_id: str,
    starts_at: datetime,
    service: str,
) -> CreateAppointmentResult:
    """Gate the write: insert pending request only — never touch `appointments`."""
    patient = get_patient(patient_id)
    aware = _ensure_aware(starts_at)

    if aware <= datetime.now(tz=CLINIC_TZ):
        raise ClinicToolError(
            CODE_INVALID_DATETIME,
            "Proposed appointment datetime must be in the future.",
            details={"datetime": aware.isoformat()},
        )

    row = db.execute_returning(
        """
        INSERT INTO appointment_requests (patient_id, starts_at, service, status)
        VALUES (%s, %s, %s, 'pending')
        RETURNING id, patient_id, starts_at, service, status, created_at
        """,
        (patient_id, aware, service.strip()),
    )

    # Safety invariant: confirmed appointments table must be untouched by this path.
    return CreateAppointmentResult(
        request=AppointmentRequest(
            request_id=int(row["id"]),
            patient_id=row["patient_id"],
            patient_name=patient["full_name"],
            starts_at=row["starts_at"],
            service=row["service"],
            status=RequestStatus(row["status"]),
            created_at=row["created_at"],
        )
    )


def count_confirmed_for_patient(patient_id: str) -> int:
    """Test helper — counts confirmed appointments (should not change on create)."""
    row = db.fetchone(
        "SELECT COUNT(*) AS n FROM appointments WHERE patient_id = %s AND status = 'confirmed'",
        (patient_id,),
    )
    return int(row["n"]) if row else 0
