-- Clinic structured records.
-- Shares the same Postgres database as docs-rag-chatbot.
-- Does NOT modify the existing `chunks` table used by hybrid retrieval.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS patients (
  patient_id   text PRIMARY KEY,
  full_name    text NOT NULL,
  email        text,
  phone        text,
  insurance    text,
  last_visit   date
);

CREATE TABLE IF NOT EXISTS appointments (
  id           bigserial PRIMARY KEY,
  patient_id   text NOT NULL REFERENCES patients (patient_id),
  starts_at    timestamptz NOT NULL,
  service      text NOT NULL,
  status       text NOT NULL DEFAULT 'confirmed'
               CHECK (status IN ('confirmed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS appointments_starts_at_idx
  ON appointments (starts_at);

CREATE INDEX IF NOT EXISTS appointments_patient_idx
  ON appointments (patient_id);

-- Write path: create_appointment only inserts here (pending).
-- Confirmed calendar rows live in `appointments` and are never written by the MCP tool.
CREATE TABLE IF NOT EXISTS appointment_requests (
  id           bigserial PRIMARY KEY,
  patient_id   text NOT NULL REFERENCES patients (patient_id),
  starts_at    timestamptz NOT NULL,
  service      text NOT NULL,
  status       text NOT NULL DEFAULT 'pending'
               CHECK (status IN ('pending', 'approved', 'rejected')),
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS appointment_requests_status_idx
  ON appointment_requests (status);
