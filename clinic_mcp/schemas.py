"""Pydantic models for every MCP tool input and structured output."""

from __future__ import annotations

from datetime import date
from datetime import datetime as DateTime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Shared domain types
# ---------------------------------------------------------------------------


class AppointmentStatus(str, Enum):
    confirmed = "confirmed"
    cancelled = "cancelled"


class RequestStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class DocChunk(BaseModel):
    """One retrieved clinic-document chunk with citation metadata."""

    source_filename: str
    doc_title: str
    chunk: str
    score: float = Field(description="Dense cosine similarity (0–1).")
    rrf_score: float = Field(description="Reciprocal-rank-fusion score.")


class AppointmentSummary(BaseModel):
    appointment_id: int
    patient_id: str
    patient_name: str | None = None
    starts_at: DateTime
    service: str
    status: AppointmentStatus = AppointmentStatus.confirmed


class PatientRecord(BaseModel):
    patient_id: str
    full_name: str
    email: str | None = None
    phone: str | None = None
    insurance: str | None = None
    last_visit: date | None = None
    upcoming_appointment: AppointmentSummary | None = None


class AppointmentRequest(BaseModel):
    request_id: int
    patient_id: str
    patient_name: str | None = None
    starts_at: DateTime
    service: str
    status: RequestStatus = RequestStatus.pending
    created_at: DateTime | None = None


# ---------------------------------------------------------------------------
# Tool inputs
# ---------------------------------------------------------------------------


class SearchClinicDocsInput(BaseModel):
    query: str = Field(
        min_length=1,
        description=(
            "Natural-language question about clinic policies, services, "
            "insurance, pricing, hours, or care instructions."
        ),
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of chunks to return when relevant sources exist.",
    )


class GetPatientRecordInput(BaseModel):
    patient_id: str = Field(
        min_length=1,
        description="Stable patient id, e.g. 'jordan-lee'.",
    )


class ListAppointmentsInput(BaseModel):
    date_from: date = Field(description="Inclusive start date (YYYY-MM-DD).")
    date_to: date = Field(description="Inclusive end date (YYYY-MM-DD).")

    @model_validator(mode="after")
    def check_range(self) -> ListAppointmentsInput:
        if self.date_to < self.date_from:
            raise ValueError("date_to must be on or after date_from")
        return self


class CreateAppointmentInput(BaseModel):
    patient_id: str = Field(min_length=1, description="Existing patient id.")
    starts_at: DateTime = Field(
        alias="datetime",
        description=(
            "Proposed appointment start (ISO-8601). Prefer timezone-aware values; "
            "naive values are interpreted in the clinic timezone."
        ),
    )
    service: str = Field(
        min_length=1,
        max_length=200,
        description="Service to book, e.g. 'Crown consult'.",
    )

    model_config = {"populate_by_name": True}

    @field_validator("service")
    @classmethod
    def strip_service(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("service must not be blank")
        return cleaned


# ---------------------------------------------------------------------------
# Tool outputs
# ---------------------------------------------------------------------------


class SearchClinicDocsResult(BaseModel):
    status: Literal["ok", "no_relevant_sources"]
    query: str
    similarity_floor: float
    best_dense_score: float
    message: str | None = None
    chunks: list[DocChunk] = Field(default_factory=list)


class GetPatientRecordResult(BaseModel):
    status: Literal["ok"] = "ok"
    patient: PatientRecord


class ListAppointmentsResult(BaseModel):
    status: Literal["ok"] = "ok"
    date_from: date
    date_to: date
    count: int
    appointments: list[AppointmentSummary]


class CreateAppointmentResult(BaseModel):
    """Write tool always returns a *pending* request — never a confirmed booking."""

    status: Literal["pending_approval"] = "pending_approval"
    message: str = (
        "Appointment request created and awaiting human approval. "
        "Nothing has been committed to the confirmed appointments calendar."
    )
    request: AppointmentRequest
