"""Postgres access — shares DATABASE_URL with docs-rag-chatbot."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector

from clinic_mcp.errors import CODE_DB_UNAVAILABLE, ClinicToolError

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://rag:rag@localhost:5432/rag")

_conn: psycopg.Connection | None = None

ROOT = Path(__file__).resolve().parent.parent


def connect(*, register: bool = True) -> psycopg.Connection:
    """Return a process-wide connection, reconnecting if closed."""
    global _conn
    try:
        if _conn is None or _conn.closed:
            _conn = psycopg.connect(DATABASE_URL)
            if register:
                register_vector(_conn)
        else:
            # Cheap liveness check — raises if the server went away.
            _conn.execute("SELECT 1")
        return _conn
    except psycopg.Error as exc:
        _conn = None
        raise ClinicToolError(
            CODE_DB_UNAVAILABLE,
            f"Clinic database is unavailable: {exc}",
        ) from exc


def reset_connection() -> None:
    """Close the cached connection (tests / after fatal errors)."""
    global _conn
    if _conn is not None and not _conn.closed:
        try:
            _conn.close()
        except psycopg.Error:
            pass
    _conn = None


def ensure_schema() -> None:
    """Create clinic tables. Does not touch the existing RAG `chunks` table."""
    schema_path = ROOT / "schema.sql"
    try:
        conn = connect(register=False)
        with conn.cursor() as cur:
            cur.execute(schema_path.read_text())
        conn.commit()
        register_vector(conn)
    except ClinicToolError:
        raise
    except psycopg.Error as exc:
        reset_connection()
        raise ClinicToolError(
            CODE_DB_UNAVAILABLE,
            f"Failed to apply clinic schema: {exc}",
        ) from exc


def seed() -> None:
    """Load deterministic BrightSmile demo patients + appointments."""
    seed_path = ROOT / "seed.sql"
    try:
        conn = connect()
        with conn.cursor() as cur:
            cur.execute(seed_path.read_text())
        conn.commit()
    except ClinicToolError:
        raise
    except psycopg.Error as exc:
        reset_connection()
        raise ClinicToolError(
            CODE_DB_UNAVAILABLE,
            f"Failed to seed clinic data: {exc}",
        ) from exc


def execute(sql: str, params=None) -> None:
    try:
        conn = connect()
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    except ClinicToolError:
        raise
    except psycopg.Error as exc:
        reset_connection()
        raise ClinicToolError(
            CODE_DB_UNAVAILABLE,
            f"Database write failed: {exc}",
        ) from exc


def fetchall(sql: str, params=None) -> list[dict]:
    try:
        conn = connect()
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description is None:
                return []
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except ClinicToolError:
        raise
    except psycopg.Error as exc:
        reset_connection()
        raise ClinicToolError(
            CODE_DB_UNAVAILABLE,
            f"Database query failed: {exc}",
        ) from exc


def fetchone(sql: str, params=None) -> dict | None:
    rows = fetchall(sql, params)
    return rows[0] if rows else None


def execute_returning(sql: str, params=None) -> dict:
    """INSERT/UPDATE … RETURNING * → single row dict."""
    try:
        conn = connect()
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description is None:
                conn.commit()
                raise ClinicToolError(
                    CODE_DB_UNAVAILABLE,
                    "Database write returned no row",
                )
            cols = [d.name for d in cur.description]
            row = cur.fetchone()
            conn.commit()
            if row is None:
                raise ClinicToolError(
                    CODE_DB_UNAVAILABLE,
                    "Database write returned no row",
                )
            return dict(zip(cols, row))
    except ClinicToolError:
        raise
    except psycopg.Error as exc:
        reset_connection()
        raise ClinicToolError(
            CODE_DB_UNAVAILABLE,
            f"Database write failed: {exc}",
        ) from exc
