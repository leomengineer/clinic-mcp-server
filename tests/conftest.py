"""Shared fixtures. Live-DB tests skip when Postgres is unreachable."""

from __future__ import annotations

import os

import pytest

# Ensure tests see the same defaults as the app
os.environ.setdefault("DATABASE_URL", "postgresql://rag:rag@localhost:5432/rag")
os.environ.setdefault("SIMILARITY_FLOOR", "0.35")
os.environ.setdefault("CLINIC_TZ", "America/Los_Angeles")


def _db_ready() -> bool:
    try:
        import psycopg

        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
    except Exception:
        return False


def _chunks_ready() -> bool:
    try:
        import psycopg

        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM chunks")
                (n,) = cur.fetchone()
            return n > 0
    except Exception:
        return False


requires_db = pytest.mark.skipif(not _db_ready(), reason="Postgres not reachable")
requires_chunks = pytest.mark.skipif(
    not _db_ready() or not _chunks_ready(),
    reason="Shared RAG chunks table empty or DB down",
)


@pytest.fixture(scope="session")
def clinic_schema():
    """Apply schema + seed once per test session when DB is up."""
    if not _db_ready():
        pytest.skip("Postgres not reachable")
    from clinic_mcp import db

    db.reset_connection()
    db.ensure_schema()
    db.seed()
    yield
    db.reset_connection()
