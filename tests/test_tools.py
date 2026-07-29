"""MCP protocol tests: tool discovery, schemas, and in-memory Client calls."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from mcp import Client

from clinic_mcp.errors import CODE_DB_UNAVAILABLE, CODE_PATIENT_NOT_FOUND, ClinicToolError
from clinic_mcp.schemas import (
    CreateAppointmentResult,
    GetPatientRecordResult,
    ListAppointmentsResult,
    PatientRecord,
    SearchClinicDocsResult,
)
from clinic_mcp.server import mcp


def _tools(result):
    """MCP Client.list_tools() returns ListToolsResult with a .tools list."""
    return result.tools if hasattr(result, "tools") else list(result)


def _schema(tool):
    return getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", {})


@pytest.mark.anyio
async def test_lists_exactly_four_tools():
    async with Client(mcp) as client:
        tools = _tools(await client.list_tools())
    names = sorted(t.name for t in tools)
    assert names == [
        "create_appointment",
        "get_patient_record",
        "list_appointments",
        "search_clinic_docs",
    ]


@pytest.mark.anyio
async def test_tool_descriptions_are_rich():
    async with Client(mcp) as client:
        tools = {t.name: t for t in _tools(await client.list_tools())}

    search = tools["search_clinic_docs"]
    assert search.description
    assert "SIMILARITY_FLOOR" in (search.description or "") or "relevant" in (
        search.description or ""
    ).lower()

    create = tools["create_appointment"]
    assert create.annotations is not None
    assert create.annotations.read_only_hint is False
    assert tools["search_clinic_docs"].annotations.read_only_hint is True


@pytest.mark.anyio
async def test_search_tool_input_schema_has_query_and_top_k():
    async with Client(mcp) as client:
        tools = {t.name: t for t in _tools(await client.list_tools())}
    schema = _schema(tools["search_clinic_docs"])
    props = schema.get("properties", {})
    assert "query" in props
    assert "top_k" in props
    assert "query" in schema.get("required", [])


@pytest.mark.anyio
async def test_create_tool_input_schema_uses_datetime_arg():
    async with Client(mcp) as client:
        tools = {t.name: t for t in _tools(await client.list_tools())}
    props = _schema(tools["create_appointment"]).get("properties", {})
    assert "datetime" in props
    assert "patient_id" in props
    assert "service" in props


@pytest.mark.anyio
async def test_malformed_top_k_becomes_tool_error():
    async with Client(mcp) as client:
        result = await client.call_tool(
            "search_clinic_docs",
            {"query": "insurance", "top_k": 999},
        )
    assert result.is_error is True


@pytest.mark.anyio
async def test_search_returns_structured_result_when_mocked():
    fake = SearchClinicDocsResult(
        status="no_relevant_sources",
        query="quantum dentistry on mars",
        similarity_floor=0.35,
        best_dense_score=0.1,
        message="No relevant sources found",
        chunks=[],
    )
    with patch("clinic_mcp.server.search_clinic_docs", return_value=fake):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "search_clinic_docs",
                {"query": "quantum dentistry on mars"},
            )
    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["status"] == "no_relevant_sources"
    assert result.structured_content["chunks"] == []


@pytest.mark.anyio
async def test_patient_not_found_is_tool_error():
    with patch(
        "clinic_mcp.server.get_patient_record",
        side_effect=ClinicToolError(CODE_PATIENT_NOT_FOUND, "No patient found"),
    ):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_patient_record",
                {"patient_id": "does-not-exist"},
            )
    assert result.is_error is True
    text = " ".join(c.text for c in result.content if hasattr(c, "text"))
    assert "patient" in text.lower() or CODE_PATIENT_NOT_FOUND in text


@pytest.mark.anyio
async def test_db_unavailable_is_tool_error_not_empty_success():
    with patch(
        "clinic_mcp.server.list_appointments",
        side_effect=ClinicToolError(CODE_DB_UNAVAILABLE, "Clinic database is unavailable"),
    ):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "list_appointments",
                {"date_from": "2026-08-01", "date_to": "2026-08-31"},
            )
    assert result.is_error is True
    text = " ".join(c.text for c in result.content if hasattr(c, "text"))
    assert "unavailable" in text.lower() or CODE_DB_UNAVAILABLE in text


@pytest.mark.anyio
async def test_get_patient_structured_success():
    fake = GetPatientRecordResult(
        patient=PatientRecord(
            patient_id="jordan-lee",
            full_name="Jordan Lee",
            insurance="Delta Dental PPO",
            last_visit=date(2026, 5, 12),
            upcoming_appointment=None,
        )
    )
    with patch("clinic_mcp.server.get_patient_record", return_value=fake):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_patient_record",
                {"patient_id": "jordan-lee"},
            )
    assert result.is_error is False
    assert result.structured_content["patient"]["patient_id"] == "jordan-lee"


@pytest.mark.anyio
async def test_create_appointment_returns_pending_only():
    from clinic_mcp.schemas import AppointmentRequest, RequestStatus

    when = datetime.now(tz=ZoneInfo("America/Los_Angeles")) + timedelta(days=7)
    fake = CreateAppointmentResult(
        request=AppointmentRequest(
            request_id=42,
            patient_id="jordan-lee",
            patient_name="Jordan Lee",
            starts_at=when,
            service="Crown consult",
            status=RequestStatus.pending,
            created_at=datetime.now(tz=ZoneInfo("America/Los_Angeles")),
        )
    )
    with patch("clinic_mcp.server.create_appointment_request", return_value=fake) as mocked:
        async with Client(mcp) as client:
            result = await client.call_tool(
                "create_appointment",
                {
                    "patient_id": "jordan-lee",
                    "datetime": when.isoformat(),
                    "service": "Crown consult",
                },
            )
    assert result.is_error is False
    assert result.structured_content["status"] == "pending_approval"
    assert result.structured_content["request"]["status"] == "pending"
    mocked.assert_called_once()


@pytest.mark.anyio
async def test_list_appointments_structured():
    fake = ListAppointmentsResult(
        date_from=date(2026, 8, 1),
        date_to=date(2026, 8, 31),
        count=0,
        appointments=[],
    )
    with patch("clinic_mcp.server.list_appointments", return_value=fake):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "list_appointments",
                {"date_from": "2026-08-01", "date_to": "2026-08-31"},
            )
    assert result.is_error is False
    assert result.structured_content["count"] == 0
