"""
DB validation script for QC Allocation Scheduler schema.

Usage:
  export DATABASE_URL=postgresql://user:pass@host:port/dbname
  python db/validate_db.py

The script checks:
- required tables exist
- unique constraint for skill matrix exists
- SLA priority check constraint exists
- audit_log trigger prevents UPDATE/DELETE

This script runs checks in transactions and rolls back to avoid leaving test rows.
"""
import os
import sys
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

REQUIRED_TABLES = [
    'users','sections','analysts','instruments','methods',
    'analyst_qualifications','shifts','analyst_shifts','jobs',
    'scheduled_tasks','blocked_slots','audit_log'
]

DB = os.environ.get('DATABASE_URL')
if not DB:
    print('ERROR: set DATABASE_URL environment variable')
    sys.exit(2)

engine = create_engine(DB)
inspector = inspect(engine)

def check_tables():
    present = inspector.get_table_names()
    missing = [t for t in REQUIRED_TABLES if t not in present]
    if missing:
        print('MISSING TABLES:', missing)
        return False
    print('All required tables present')
    return True

def check_unique_skill_constraint():
    # analyst_qualifications should have unique constraint on (analyst_id, method_id, instrument_type)
    uq = inspector.get_unique_constraints('analyst_qualifications')
    names = [c.get('name') for c in uq]
    found = any('analyst' in (n or '') and 'method' in (n or '') for n in names)
    if not found:
        print('WARNING: expected unique constraint on (analyst_id,method_id,instrument_type) not found. Constraints:', names)
        return False
    print('Unique constraint for skill matrix appears present:', names)
    return True

def check_sla_check_constraint():
    # jobs should have check constraint ck_supply_chain_priority_range
    checks = inspector.get_check_constraints('jobs')
    names = [c.get('name') for c in checks]
    if 'ck_supply_chain_priority_range' not in names:
        print('WARNING: SLA supply_chain_priority check constraint missing. Found:', names)
        return False
    print('SLA supply_chain_priority check constraint present')
    return True

def check_audit_trigger():
    # Attempt to insert then UPDATE an audit_log row inside a transaction and expect trigger to raise
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            res = conn.execute(text("INSERT INTO audit_log(actor_id, action, target_type, payload, hash) VALUES (NULL, 'validate_insert', 'db', '{}'::jsonb, md5(now()::text)) RETURNING id"))
            row = res.fetchone()
            if not row:
                print('Could not insert test audit row')
                trans.rollback()
                return False
            aid = row[0]
            try:
                conn.execute(text('UPDATE audit_log SET action = :a WHERE id = :id'), {'a': 'attempt_update', 'id': aid})
                print('ERROR: audit_log update succeeded; trigger may be missing')
                trans.rollback()
                return False
            except DBAPIError as e:
                # Expected: trigger prevented update
                print('Audit trigger prevented modification as expected:', str(e).splitlines()[0])
                trans.rollback()
                return True
        except Exception as e:
            print('Error during audit trigger test:', e)
            try:
                trans.rollback()
            except Exception:
                pass
            return False

def check_sla_constraint_violation():
    # Try to insert a job with invalid supply_chain_priority > 10 and expect check constraint error
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            try:
                conn.execute(text(
                    "INSERT INTO jobs(sample_id, method_id, material, supply_chain_priority, created_at) \
                     VALUES ('VALIDATE-1', (SELECT id FROM methods LIMIT 1), 'FG', 999, now())"
                ))
                print('ERROR: invalid job insert succeeded; check constraint may be missing')
                trans.rollback()
                return False
            except DBAPIError as e:
                print('SLA check constraint enforced (insert rejected):', str(e).splitlines()[0])
                trans.rollback()
                return True
        except Exception as e:
            print('Error during SLA constraint test:', e)
            try:
                trans.rollback()
            except Exception:
                pass
            return False

if __name__ == '__main__':
    ok = True
    print('Connecting to', DB)
    ok = check_tables() and ok
    ok = check_unique_skill_constraint() and ok
    ok = check_sla_check_constraint() and ok
    ok = check_audit_trigger() and ok
    ok = check_sla_constraint_violation() and ok

    if ok:
        print('\nDB validation PASSED')
        sys.exit(0)
    else:
        print('\nDB validation FAILED')
        sys.exit(1)
