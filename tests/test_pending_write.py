"""Live-DB tests for structured records and the pending-only write invariant."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch

import pytest

from clinic_mcp.errors import CODE_DB_UNAVAILABLE, CODE_PATIENT_NOT_FOUND, ClinicToolError
from clinic_mcp.records import (
    CLINIC_TZ,
    count_confirmed_for_patient,
    create_appointment_request,
    get_patient_record,
    list_appointments,
)
from tests.conftest import requires_db


@requires_db
def test_get_jordan_lee(clinic_schema):
    result = get_patient_record("jordan-lee")
    assert result.patient.patient_id == "jordan-lee"
    assert result.patient.full_name == "Jordan Lee"
    assert result.patient.insurance and "Delta" in result.patient.insurance
    # Seed includes a future crown consult on 2026-08-05
    assert result.patient.upcoming_appointment is not None
    assert "Crown" in result.patient.upcoming_appointment.service


@requires_db
def test_unknown_patient_raises(clinic_schema):
    with pytest.raises(ClinicToolError) as exc:
        get_patient_record("no-such-patient")
    assert exc.value.code == CODE_PATIENT_NOT_FOUND


@requires_db
def test_list_appointments_august_2026(clinic_schema):
    result = list_appointments(date(2026, 8, 1), date(2026, 8, 31))
    assert result.count >= 1
    ids = {a.patient_id for a in result.appointments}
    assert "jordan-lee" in ids


@requires_db
def test_list_appointments_empty_window_is_ok_not_error(clinic_schema):
    result = list_appointments(date(2030, 1, 1), date(2030, 1, 2))
    assert result.status == "ok"
    assert result.count == 0
    assert result.appointments == []


@requires_db
def test_create_appointment_pending_does_not_touch_confirmed(clinic_schema):
    before = count_confirmed_for_patient("jordan-lee")
    when = datetime.now(tz=CLINIC_TZ) + timedelta(days=14)
    when = when.replace(hour=15, minute=0, second=0, microsecond=0)

    result = create_appointment_request(
        patient_id="jordan-lee",
        starts_at=when,
        service="Crown consult",
    )

    assert result.status == "pending_approval"
    assert result.request.status.value == "pending"
    assert result.request.patient_id == "jordan-lee"
    assert result.request.service == "Crown consult"
    assert "awaiting human approval" in result.message.lower()

    after = count_confirmed_for_patient("jordan-lee")
    assert after == before, "create_appointment must not insert into appointments"


@requires_db
def test_create_appointment_rejects_past_datetime(clinic_schema):
    past = datetime(2020, 1, 1, 10, 0, tzinfo=CLINIC_TZ)
    with pytest.raises(ClinicToolError) as exc:
        create_appointment_request("jordan-lee", past, "Cleaning")
    assert exc.value.code == "invalid_datetime"


def test_db_failure_surfaces_structured_code():
    """Infrastructure failure must raise — never look like an empty calendar."""
    with patch(
        "clinic_mcp.records.db.fetchall",
        side_effect=ClinicToolError(CODE_DB_UNAVAILABLE, "Clinic database is unavailable"),
    ):
        with pytest.raises(ClinicToolError) as exc:
            list_appointments(date(2026, 8, 1), date(2026, 8, 31))
    assert exc.value.code == CODE_DB_UNAVAILABLE
