"""Structured tool errors with stable codes for the model to act on."""

from __future__ import annotations


class ClinicToolError(Exception):
    """Raised from tools so Claude sees is_error=True with a clear code + message.

    Never return empty results for infrastructure failures — raise this instead.
    """

    def __init__(self, code: str, message: str, *, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"[{code}] {message}")


# Stable codes used across tools
CODE_DB_UNAVAILABLE = "db_unavailable"
CODE_PATIENT_NOT_FOUND = "patient_not_found"
CODE_INVALID_DATE_RANGE = "invalid_date_range"
CODE_INVALID_DATETIME = "invalid_datetime"
CODE_VALIDATION = "validation_error"
