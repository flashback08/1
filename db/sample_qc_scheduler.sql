-- Sample PostgreSQL schema and seed data for QC Allocation Scheduler
-- Save as db/sample_qc_scheduler.sql

-- Requires: pgcrypto for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Users / Roles
CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  username text UNIQUE NOT NULL,
  display_name text,
  email text UNIQUE,
  role text NOT NULL CHECK (role IN ('planner','admin','qa_viewer')),
  password_hash text NOT NULL,
  totp_secret text,
  created_at timestamptz DEFAULT now()
);

-- Sections
CREATE TABLE IF NOT EXISTS sections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL
);

-- Analysts
CREATE TABLE IF NOT EXISTS analysts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid UNIQUE REFERENCES users(id) ON DELETE SET NULL,
  section_id uuid REFERENCES sections(id),
  active boolean DEFAULT true
);

-- Instruments
CREATE TABLE IF NOT EXISTS instruments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  type text NOT NULL,
  model text,
  status text NOT NULL CHECK (status IN ('available','calibration','repair','decommissioned')),
  last_calibrated timestamptz,
  next_calibration_due timestamptz,
  protected_time jsonb DEFAULT '[]'::jsonb
);

-- Methods
CREATE TABLE IF NOT EXISTS methods (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text UNIQUE NOT NULL,
  name text NOT NULL,
  steps jsonb NOT NULL,
  estimated_active_minutes int NOT NULL
);

-- Analyst qualifications
CREATE TABLE IF NOT EXISTS analyst_qualifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  analyst_id uuid REFERENCES analysts(id) ON DELETE CASCADE,
  method_id uuid REFERENCES methods(id) ON DELETE CASCADE,
  instrument_type text NOT NULL,
  UNIQUE(analyst_id, method_id, instrument_type)
);

-- Shifts
CREATE TABLE IF NOT EXISTS shifts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text,
  start_time time NOT NULL,
  end_time time NOT NULL
);

CREATE TABLE IF NOT EXISTS analyst_shifts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  analyst_id uuid REFERENCES analysts(id),
  shift_id uuid REFERENCES shifts(id),
  start_date date NOT NULL,
  end_date date
);

-- Material type enum substitute
-- Jobs (pending workload)
CREATE TYPE IF NOT EXISTS material_type AS ENUM ('FG','RM','PM','Stability','IPQC','Micro');

CREATE TABLE IF NOT EXISTS jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sample_id text NOT NULL,
  method_id uuid REFERENCES methods(id) NOT NULL,
  material material_type NOT NULL,
  quantity int DEFAULT 1,
  sla_date timestamptz,
  supply_chain_priority int DEFAULT 0,
  ipqc_status text,
  campaign_group_key text,
  created_at timestamptz DEFAULT now(),
  requested_by uuid REFERENCES users(id)
);

-- Scheduled tasks
CREATE TABLE IF NOT EXISTS scheduled_tasks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id uuid REFERENCES jobs(id) NOT NULL,
  method_id uuid REFERENCES methods(id) NOT NULL,
  analyst_id uuid REFERENCES analysts(id) NOT NULL,
  instrument_id uuid REFERENCES instruments(id) NOT NULL,
  start_time timestamptz NOT NULL,
  end_time timestamptz NOT NULL,
  step jsonb,
  status text NOT NULL CHECK (status IN ('planned','in-progress','completed','cancelled')),
  created_at timestamptz DEFAULT now()
);

-- Blocked slots for callbacks
CREATE TABLE IF NOT EXISTS blocked_slots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  scheduled_task_id uuid REFERENCES scheduled_tasks(id) ON DELETE CASCADE,
  blocked_start timestamptz NOT NULL,
  blocked_end timestamptz NOT NULL,
  reason text
);

-- Audit log with chained hash
CREATE TABLE IF NOT EXISTS audit_log (
  id bigserial PRIMARY KEY,
  event_id uuid DEFAULT gen_random_uuid(),
  actor_id uuid REFERENCES users(id),
  action text NOT NULL,
  target_type text,
  target_id uuid,
  payload jsonb,
  created_at timestamptz DEFAULT now(),
  prev_hash text,
  hash text NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_jobs_sla ON jobs (sla_date);
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_range ON scheduled_tasks USING btree (start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_instruments_type_status ON instruments(type, status);

-- Sample seed data
-- Users
INSERT INTO users(username, display_name, email, role, password_hash, totp_secret)
VALUES
('alice.planner','Alice Planner','alice@example.com','planner','$2b$12$examplehash','TOTPSECRET1'),
('bob.admin','Bob Admin','bob@example.com','admin','$2b$12$examplehash','TOTPSECRET2'),
('carol.qa','Carol QA','carol@example.com','qa_viewer','$2b$12$examplehash','TOTPSECRET3')
ON CONFLICT (username) DO NOTHING;

-- Sections
INSERT INTO sections(name) VALUES ('Chemistry'), ('Microbiology') ON CONFLICT DO NOTHING;

-- Analysts (link to users)
INSERT INTO analysts(user_id, section_id, active)
SELECT id, (SELECT id FROM sections WHERE name='Chemistry' LIMIT 1), true FROM users WHERE username='alice.planner' ON CONFLICT DO NOTHING;

INSERT INTO analysts(user_id, section_id, active)
SELECT id, (SELECT id FROM sections WHERE name='Microbiology' LIMIT 1), true FROM users WHERE username='carol.qa' ON CONFLICT DO NOTHING;

-- Instruments
INSERT INTO instruments(name,type,model,status,last_calibrated,next_calibration_due,protected_time)
VALUES
('HPLC-1','HPLC','Agilent 1200','available', now() - interval '7 days', now() + interval '83 days', '[{"dow":1,"start":"08:00","end":"09:00"}]'),
('GC-1','GC','Shimadzu GC','available', now() - interval '30 days', now() + interval '150 days', '[]')
ON CONFLICT DO NOTHING;

-- Methods
INSERT INTO methods(code,name,steps,estimated_active_minutes)
VALUES
('M-HPLC-01','Assay HPLC','[{"step":"prep","active_minutes":30},{"step":"run","active_minutes":45},{"step":"wait","wait_days":3}]',75),
('M-MIC-01','Microbial Plate Count','[{"step":"prep","active_minutes":15},{"step":"incubate","wait_days":5},{"step":"read","active_minutes":10}]',25)
ON CONFLICT DO NOTHING;

-- Link qualifications: find analyst ids
WITH a AS (SELECT id FROM analysts JOIN users u ON u.id=analysts.user_id WHERE u.username='alice.planner')
INSERT INTO analyst_qualifications(analyst_id, method_id, instrument_type)
SELECT a.id, m.id, 'HPLC' FROM a CROSS JOIN methods m WHERE m.code='M-HPLC-01'
ON CONFLICT DO NOTHING;

-- Shifts
INSERT INTO shifts(name,start_time,end_time) VALUES
('Day', '08:00:00','17:00:00'),
('Swing','14:00:00','23:00:00') ON CONFLICT DO NOTHING;

-- Analyst Shifts: assign Alice to Day shift
INSERT INTO analyst_shifts(analyst_id, shift_id, start_date)
SELECT analysts.id, shifts.id, CURRENT_DATE FROM analysts, shifts, users
WHERE users.username='alice.planner' AND analysts.user_id=users.id AND shifts.name='Day'
ON CONFLICT DO NOTHING;

-- Jobs
INSERT INTO jobs(sample_id, method_id, material, quantity, sla_date, supply_chain_priority, ipqc_status, campaign_group_key, requested_by)
VALUES
('SMP-001',(SELECT id FROM methods WHERE code='M-HPLC-01'),'FG',10, now() + interval '2 days', 2, NULL, 'CAMPAIGN-A',(SELECT id FROM users WHERE username='alice.planner'),
('SMP-002',(SELECT id FROM methods WHERE code='M-HPLC-01'),'FG',5, now() + interval '1 day', 5, 'critical','CAMPAIGN-A',(SELECT id FROM users WHERE username='bob.admin'),
('SMP-003',(SELECT id FROM methods WHERE code='M-MIC-01'),'Micro',3, now() + interval '7 days', 0, NULL,NULL,(SELECT id FROM users WHERE username='carol.qa')
ON CONFLICT DO NOTHING;

-- Example scheduled task (seed)
INSERT INTO scheduled_tasks(job_id, method_id, analyst_id, instrument_id, start_time, end_time, step, status)
VALUES (
  (SELECT id FROM jobs WHERE sample_id='SMP-002'),
  (SELECT id FROM methods WHERE code='M-HPLC-01'),
  (SELECT id FROM analysts JOIN users ON users.id=analysts.user_id WHERE users.username='alice.planner'),
  (SELECT id FROM instruments WHERE type='HPLC' LIMIT 1),
  now() + interval '2 hours', now() + interval '3 hours', '{"step":"run"}', 'planned'
)
ON CONFLICT DO NOTHING;

-- Example blocked slot for multi-day callback
INSERT INTO blocked_slots(scheduled_task_id, blocked_start, blocked_end, reason)
VALUES (
  (SELECT id FROM scheduled_tasks WHERE step->> 'step' = 'run' LIMIT 1),
  now() + interval '3 days', now() + interval '3 days' + interval '1 hour', 'Day3 callback'
)
ON CONFLICT DO NOTHING;

-- Example audit entry (application should compute chained hash in production)
INSERT INTO audit_log(actor_id, action, target_type, target_id, payload, prev_hash, hash)
VALUES (
  (SELECT id FROM users WHERE username='alice.planner'),
  'seed:initial_import', 'database','00000000-0000-0000-0000-000000000000',
  jsonb_build_object('note','seed data loaded'), NULL, md5(now()::text)
);

-- Quick usage note (run from project root):
-- psql -d yourdb -f db/sample_qc_scheduler.sql

