"""Unit tests for Pydantic input validation — no database required."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from clinic_mcp.schemas import (
    CreateAppointmentInput,
    ListAppointmentsInput,
    SearchClinicDocsInput,
)


def test_search_docs_rejects_empty_query():
    with pytest.raises(ValidationError):
        SearchClinicDocsInput(query="")


def test_search_docs_rejects_top_k_out_of_bounds():
    with pytest.raises(ValidationError):
        SearchClinicDocsInput(query="insurance", top_k=0)
    with pytest.raises(ValidationError):
        SearchClinicDocsInput(query="insurance", top_k=50)


def test_search_docs_defaults_top_k():
    m = SearchClinicDocsInput(query="Delta Dental")
    assert m.top_k == 5


def test_list_appointments_rejects_inverted_range():
    with pytest.raises(ValidationError) as exc:
        ListAppointmentsInput(date_from=date(2026, 8, 10), date_to=date(2026, 8, 1))
    assert "date_to" in str(exc.value).lower() or "date_from" in str(exc.value).lower()


def test_list_appointments_accepts_same_day():
    m = ListAppointmentsInput(date_from=date(2026, 8, 5), date_to=date(2026, 8, 5))
    assert m.date_from == m.date_to


def test_create_appointment_rejects_blank_service():
    with pytest.raises(ValidationError):
        CreateAppointmentInput(
            patient_id="jordan-lee",
            datetime=datetime(2026, 8, 12, 10, 0, tzinfo=ZoneInfo("America/Los_Angeles")),
            service="   ",
        )


def test_create_appointment_strips_service():
    m = CreateAppointmentInput(
        patient_id="jordan-lee",
        datetime=datetime(2026, 8, 12, 10, 0, tzinfo=ZoneInfo("America/Los_Angeles")),
        service="  Crown consult  ",
    )
    assert m.service == "Crown consult"
    assert m.starts_at.year == 2026
