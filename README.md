# clinic-mcp-server

**MCP Server: Company Data as Claude Tools.**

Expose a clinic's knowledge base and structured records to Claude Desktop (or any MCP client) as callable tools — with the same grounding discipline as [docs-rag-chatbot](../docs-rag-chatbot): **read tools grounded with citations; write tools gated behind approval.**

That contrast is the pitch. Anyone can wrap a search endpoint. Showing you thought about what happens when an agent can *change* something is what senior looks like.

## Architecture

```
Claude Desktop (stdio MCP)
        │
        ▼
 clinic-mcp-server
   ├─ search_clinic_docs  → hybrid RRF over shared `chunks` (pgvector + tsvector)
   │                         + SIMILARITY_FLOOR gate → citations or "no relevant sources"
   ├─ get_patient_record  → Postgres `patients` (+ next confirmed appointment)
   ├─ list_appointments   → parameterized date-range query on `appointments`
   └─ create_appointment  → INSERT into `appointment_requests` (pending only)
                             NEVER writes confirmed `appointments`
```

Shares `DATABASE_URL` with docs-rag-chatbot (same Postgres). Retrieval code is local; the RAG `chunks` table is reused as-is. Clinic tables (`patients`, `appointments`, `appointment_requests`) are additive.

## Prerequisites

1. Postgres/pgvector running for [docs-rag-chatbot](../docs-rag-chatbot) with docs ingested (`make up && make ingest` there).
2. Python 3.12 + [uv](https://github.com/astral-sh/uv).

## Quick start (two minutes)

```bash
cd clinic-mcp-server
uv sync
cp .env.example .env   # DATABASE_URL should match docs-rag-chatbot

# Create clinic tables + seed Jordan Lee et al. (does not touch chunks)
make setup

# Smoke-test over stdio (or point Claude Desktop at it — see below)
make serve
```

### Claude Desktop config

Add this to your Claude Desktop `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`). Use **absolute** paths:

```json
{
  "mcpServers": {
    "clinic": {
      "command": "/Users/leovet/.cargo/bin/uv",
      "args": [
        "run",
        "--directory",
        "/Users/leovet/freelance/clinic-mcp-server",
        "python",
        "-m",
        "clinic_mcp"
      ]
    }
  }
}
```

Restart Claude Desktop. You should see four tools under the clinic server.

A ready-to-merge example lives at [`claude_desktop_config.example.json`](claude_desktop_config.example.json).

> Tip: find `uv` with `which uv` if your install path differs.

## Demo (~60s)

1. Open Claude Desktop with the MCP server connected — show the four tools.
2. Ask: **"Do you accept Delta Dental PPO?"**  
   → Claude calls `search_clinic_docs`, answers with a source citation (e.g. `06_insurance_faq.md`).
3. Ask: **"when is Jordan Lee's next appointment?"**  
   → Claude calls `get_patient_record` with `jordan-lee`, returns structured data (insurance, upcoming crown consult).
4. Ask: **"book Jordan a crown consult next Tuesday"**  
   → Claude calls `create_appointment`; response is `pending_approval` — nothing committed to the confirmed calendar.
5. Close: **"Read tools answer. The write tool proposes and waits for a human."**

## Tools

| Tool | Mode | Behavior |
|------|------|----------|
| `search_clinic_docs(query, top_k=5)` | read | Hybrid retrieval; below `SIMILARITY_FLOOR` returns `status=no_relevant_sources` (empty chunks) — Claude must not invent. |
| `get_patient_record(patient_id)` | read | Patient row + next confirmed appointment. Missing patient / DB down → tool error (not empty success). |
| `list_appointments(date_from, date_to)` | read | Confirmed appointments in an inclusive date window (clinic TZ). Empty list is valid; DB failure is an error. |
| `create_appointment(patient_id, datetime, service)` | write (gated) | Inserts `appointment_requests.status='pending'` only. Returns `pending_approval`. |

Demo patient id: **`jordan-lee`**.

## Config (`.env`)

| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_URL` | Shared Postgres (same as RAG app) | `postgresql://rag:rag@localhost:5432/rag` |
| `SIMILARITY_FLOOR` | Dense cosine gate for doc search | `0.35` |
| `CLINIC_TZ` | Timezone for date windows / naive datetimes | `America/Los_Angeles` |

## Makefile

```bash
make sync     # uv sync --extra dev
make setup    # schema + seed
make schema   # clinic tables only
make seed     # demo patients / appointments
make serve    # stdio MCP server
make test     # pytest
```

## Safety contract

- **Grounded reads:** `search_clinic_docs` refuses weak matches instead of returning noise Claude could cite.
- **Loud failures:** DB outages raise `[db_unavailable] …` tool errors. Empty appointment lists are only returned when the query succeeded.
- **Guarded writes:** `create_appointment` never inserts into `appointments`. A human must approve the pending request before anything is confirmed.
- **Out of scope (intentionally):** auth, multi-tenancy, OAuth, remote hosting, MCP resources/prompts. Four tools done well beats twelve half-wired.

## Tests

```bash
make test
```

Covers tool discovery/schemas, Pydantic validation, retrieval gate + citations, structured errors, patient/appointment lookups, and the invariant that write calls create pending requests only.
