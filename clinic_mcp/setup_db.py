"""CLI helpers: apply schema + seed against the shared RAG database."""

from __future__ import annotations

import argparse
import sys

from clinic_mcp import db


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clinic MCP database setup")
    parser.add_argument(
        "command",
        choices=["schema", "seed", "setup"],
        help="schema = create tables; seed = load demo data; setup = both",
    )
    args = parser.parse_args(argv)

    if args.command in ("schema", "setup"):
        db.ensure_schema()
        print("Clinic schema applied (patients, appointments, appointment_requests).")
    if args.command in ("seed", "setup"):
        db.seed()
        print("Demo patients + appointments seeded (jordan-lee et al.).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
