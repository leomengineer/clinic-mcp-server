-- Deterministic BrightSmile demo data for MCP tools.
-- Safe to re-run: upserts patients, clears and reloads appointments/requests.

INSERT INTO patients (patient_id, full_name, email, phone, insurance, last_visit)
VALUES
  (
    'jordan-lee',
    'Jordan Lee',
    'jordan.lee@example.com',
    '(951) 555-0142',
    'Delta Dental PPO',
    '2026-05-12'
  ),
  (
    'maria-vargas',
    'Maria Elena Vargas',
    'maria.vargas@example.com',
    '(951) 555-0188',
    'MetLife PDP',
    '2026-03-03'
  ),
  (
    'sam-okonkwo',
    'Sam Okonkwo',
    'sam.okonkwo@example.com',
    '(951) 555-0117',
    'Cash / no insurance',
    '2026-06-20'
  ),
  (
    'ava-chen',
    'Ava Chen',
    'ava.chen@example.com',
    '(951) 555-0199',
    'Cigna DPPO',
    '2026-01-15'
  )
ON CONFLICT (patient_id) DO UPDATE SET
  full_name  = EXCLUDED.full_name,
  email      = EXCLUDED.email,
  phone      = EXCLUDED.phone,
  insurance  = EXCLUDED.insurance,
  last_visit = EXCLUDED.last_visit;

DELETE FROM appointment_requests;
DELETE FROM appointments;

INSERT INTO appointments (patient_id, starts_at, service, status) VALUES
  ('jordan-lee',  '2026-08-05 10:00:00-07', 'Crown consult',     'confirmed'),
  ('jordan-lee',  '2026-04-02 09:30:00-07', 'Cleaning + exam',   'confirmed'),
  ('maria-vargas','2026-08-07 14:00:00-07', 'Root canal follow-up','confirmed'),
  ('sam-okonkwo', '2026-08-12 11:00:00-07', 'Whitening consult', 'confirmed'),
  ('ava-chen',    '2026-07-30 08:30:00-07', 'New patient exam',  'confirmed'),
  ('ava-chen',    '2026-09-01 13:00:00-07', 'Periodontal therapy','confirmed');
