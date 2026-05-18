QC Allocation Scheduler
======================

Overview
--------
A compact Planner-only web tool for scheduling QC lab workload: matches qualified analysts and calibrated instruments to highest-priority tasks, supports campaign batching, multi-day tests, and Part 11-style auditability. This repo contains DB schema, SQL seeds, Alembic migrations, and a small validation helper.

Repository layout
-----------------
- `db/` — SQL artifacts and DB helper scripts
  - `sample_qc_scheduler.sql` — schema + seed sample
  - `sample_qc_schema_create_only.sql` — CREATE-only schema (no seed)
  - `validate_db.py` — checks table presence, constraints, audit trigger behavior
  - `models.py` — SQLAlchemy ORM models (in `db/models.py`)
- `migrations/` — Alembic migration scripts and `env.py`
- `alembic.ini` — Alembic configuration

Quick start (DB)
----------------
1. Create a Postgres database and set `DATABASE_URL`:

```bash
export DATABASE_URL=postgresql://user:pass@host:5432/qc_scheduler
```

2a. Apply migrations (recommended):

```bash
pip install alembic psycopg2-binary
alembic -c alembic.ini upgrade head
```

2b. Or run the CREATE+seed SQL (quick demo):

```bash
psql -d $DATABASE_URL -f db/sample_qc_scheduler.sql
```

Validation
----------
Run the validator to confirm schema + protections:

```bash
python db/validate_db.py
```

Schema highlights
-----------------
- Skill matrix (analyst qualifications): enforced by unique constraint on `(analyst_id, method_id, instrument_type)` implemented in `analyst_qualifications` (DB: `uq_analyst_method_instrument`). This prevents duplicate/ambiguous qualification entries.
- SLA / Supply Chain priority: `jobs.supply_chain_priority` has a DB-level check constraint limiting values (0–10) (`ck_supply_chain_priority_range`). Keep application weights consistent with this range.
- Audit trail: immutable `audit_log` table with `prev_hash`/`hash` fields. A DB trigger prevents UPDATE/DELETE at the DB layer; application is expected to compute and store a chained hash on insert for tamper evidence.
- Multi-day tests: modeled via `scheduled_tasks` and `blocked_slots` to reserve callback windows (Day0/Day3/Day5) without occupying full instrument time.
- Instruments: `protected_time` stored as JSON (recurring daily blocks) and respected by scheduler availability logic.

Security & Part 11 considerations
--------------------------------
- Authentication: local username/password + TOTP for privileged roles. Store `totp_secret` encrypted at rest.
- E-signature: capture `esig_user_id`, `esig_timestamp`, `esig_reason` (not yet in schema) when required; write signed actions to `audit_log`.
- Audit immutability: enforce at DB (trigger) and application levels. Retain exports, retention, and WORM storage policies outside DB for compliance.

Developer notes
---------------
- SQLAlchemy models are in `db/models.py`; Alembic uses `migrations/env.py` which imports `Base.metadata`.
- For heavy re-plans or overnight global optimization, consider running an ILP solver (CBC/Gurobi) off-thread; keep the planner endpoint asynchronous.

Next steps (suggested)
----------------------
- Implement server-side endpoints (`/api/planner/day`, `/api/schedule/plan`, `/api/schedule/replan`).
- Implement `esig` fields and UI capture for signed changes.
- Create React `GanttPlanner` components and wire drag/resize events to `PATCH /api/schedule/task/{id}`.

Contact
-------
If you want me to scaffold the FastAPI backend or the React `GanttPlanner` component tree next, tell me which to start with.