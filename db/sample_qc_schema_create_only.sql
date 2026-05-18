-- PostgreSQL CREATE-only schema for QC Allocation Scheduler
-- No seed data in this file.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Users / Roles
CREATE TABLE users (
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
CREATE TABLE sections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL
);

-- Analysts
CREATE TABLE analysts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid UNIQUE REFERENCES users(id) ON DELETE SET NULL,
  section_id uuid REFERENCES sections(id),
  active boolean DEFAULT true
);

-- Instruments
CREATE TABLE instruments (
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
CREATE TABLE methods (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text UNIQUE NOT NULL,
  name text NOT NULL,
  steps jsonb NOT NULL,
  estimated_active_minutes int NOT NULL
);

-- Analyst qualifications
CREATE TABLE analyst_qualifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  analyst_id uuid REFERENCES analysts(id) ON DELETE CASCADE,
  method_id uuid REFERENCES methods(id) ON DELETE CASCADE,
  instrument_type text NOT NULL,
  UNIQUE(analyst_id, method_id, instrument_type)
);

-- Shifts and roster
CREATE TABLE shifts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text,
  start_time time NOT NULL,
  end_time time NOT NULL
);

CREATE TABLE analyst_shifts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  analyst_id uuid REFERENCES analysts(id),
  shift_id uuid REFERENCES shifts(id),
  start_date date NOT NULL,
  end_date date
);

-- Material type
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'material_type') THEN
    CREATE TYPE material_type AS ENUM ('FG','RM','PM','Stability','IPQC','Micro');
  END IF;
END$$;

-- Jobs (pending workload)
CREATE TABLE jobs (
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
CREATE TABLE scheduled_tasks (
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

-- Blocked slots for dependent callbacks (multi-day tests)
CREATE TABLE blocked_slots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  scheduled_task_id uuid REFERENCES scheduled_tasks(id) ON DELETE CASCADE,
  blocked_start timestamptz NOT NULL,
  blocked_end timestamptz NOT NULL,
  reason text
);

-- Audit log (append-only). In production compute chained hash in application layer.
CREATE TABLE audit_log (
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

-- Indexes for performance
CREATE INDEX idx_jobs_sla ON jobs (sla_date);
CREATE INDEX idx_scheduled_tasks_range ON scheduled_tasks USING btree (start_time, end_time);
CREATE INDEX idx_instruments_type_status ON instruments(type, status);

-- Notes:
-- 1) Store TOTP secrets encrypted at rest; password_hash must use a strong hashing algorithm (bcrypt/argon2).
-- 2) For Part 11 e-signatures, augment `audit_log` with explicit esig fields when capturing signed actions.
-- 3) Application should enforce immutability of `audit_log` (no DELETE/UPDATE).

-- End of CREATE-only schema
