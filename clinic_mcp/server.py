"""Clinic MCP Server — four tools over BrightSmile docs + structured records.

Built on FastMCP (stdio for Claude Desktop). Read tools are grounded; the write
tool only creates a pending approval request.
"""

from __future__ import annotations

from datetime import date
from datetime import datetime as DateTime
from typing import Annotated

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from clinic_mcp.records import (
    create_appointment_request,
    get_patient_record,
    list_appointments,
)
from clinic_mcp.retrieval import search_clinic_docs
from clinic_mcp.schemas import (
    CreateAppointmentResult,
    GetPatientRecordResult,
    ListAppointmentsResult,
    SearchClinicDocsResult,
)

mcp = FastMCP(
    "clinic-mcp-server",
    instructions=(
        "BrightSmile Dental Clinic tools. "
        "Use search_clinic_docs for policy/insurance/pricing questions and cite source filenames. "
        "If search returns status=no_relevant_sources, say you don't have that in clinic documents — do not invent. "
        "Use get_patient_record and list_appointments for structured patient/schedule data. "
        "create_appointment only proposes a booking (pending_approval); a human must approve before it is confirmed."
    ),
)


@mcp.tool(
    name="search_clinic_docs",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        openWorldHint=False,
        destructiveHint=False,
    ),
)
def search_clinic_docs_tool(
    query: Annotated[
        str,
        Field(
            min_length=1,
            description=(
                "Natural-language question about BrightSmile policies, services, "
                "insurance networks, pricing, hours, booking rules, or care instructions."
            ),
        ),
    ],
    top_k: Annotated[
        int,
        Field(
            ge=1,
            le=20,
            description="Max chunks to return when the relevance gate passes (default 5).",
        ),
    ] = 5,
) -> SearchClinicDocsResult:
    """Hybrid-search the clinic knowledge base (pgvector + full-text, RRF-fused).

    Returns cited chunks with source filename and scores when the best dense
    similarity clears the SIMILARITY_FLOOR gate. Below that floor, returns
    status=no_relevant_sources with an empty chunk list — do not fabricate
    an answer from weak matches.
    """
    return search_clinic_docs(query=query, top_k=top_k)


@mcp.tool(
    name="get_patient_record",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        openWorldHint=False,
        destructiveHint=False,
    ),
)
def get_patient_record_tool(
    patient_id: Annotated[
        str,
        Field(
            min_length=1,
            description="Stable patient id. Demo patient: 'jordan-lee'.",
        ),
    ],
) -> GetPatientRecordResult:
    """Look up a patient by id: name, insurance, last visit, and next confirmed appointment.

    Raises a tool error if the patient does not exist or the database is down —
    never returns an empty success that could be mistaken for 'no appointments'.
    """
    return get_patient_record(patient_id)


@mcp.tool(
    name="list_appointments",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        openWorldHint=False,
        destructiveHint=False,
    ),
)
def list_appointments_tool(
    date_from: Annotated[
        date,
        Field(description="Inclusive range start (YYYY-MM-DD), clinic local calendar."),
    ],
    date_to: Annotated[
        date,
        Field(description="Inclusive range end (YYYY-MM-DD), clinic local calendar."),
    ],
) -> ListAppointmentsResult:
    """List confirmed appointments between date_from and date_to (inclusive).

    date_to must be on or after date_from. Empty list with status=ok means no
    confirmed appointments in that window — distinct from a database failure,
    which raises a tool error.
    """
    return list_appointments(date_from=date_from, date_to=date_to)


@mcp.tool(
    name="create_appointment",
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
def create_appointment_tool(
    patient_id: Annotated[
        str,
        Field(min_length=1, description="Existing patient id, e.g. 'jordan-lee'."),
    ],
    datetime: Annotated[  # noqa: A002 — public tool arg name matches the spec
        DateTime,
        Field(
            description=(
                "Proposed start time (ISO-8601). Prefer timezone-aware values; "
                "naive values use the clinic timezone (America/Los_Angeles)."
            ),
        ),
    ],
    service: Annotated[
        str,
        Field(
            min_length=1,
            max_length=200,
            description="Service to book, e.g. 'Crown consult'.",
        ),
    ],
) -> CreateAppointmentResult:
    """Propose a new appointment — does NOT confirm it.

    Inserts a row into appointment_requests with status=pending and returns
    pending_approval. A human must approve before anything lands on the
    confirmed appointments calendar. Calling this twice creates two pending
    requests; it never silently books.
    """
    return create_appointment_request(
        patient_id=patient_id,
        starts_at=datetime,
        service=service,
    )


def main() -> None:
    """stdio entry point for Claude Desktop / any MCP client."""
    mcp.run()


if __name__ == "__main__":
    main()
