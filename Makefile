.PHONY: sync schema seed setup serve test

sync:
	uv sync --extra dev

schema:
	uv run python -m clinic_mcp.setup_db schema

seed:
	uv run python -m clinic_mcp.setup_db seed

setup:
	uv run python -m clinic_mcp.setup_db setup

serve:
	uv run python -m clinic_mcp

test:
	uv sync --extra dev
	uv run pytest
