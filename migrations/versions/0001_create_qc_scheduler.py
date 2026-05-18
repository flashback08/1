"""create qc scheduler schema

Revision ID: 0001_create_qc_scheduler
Revises: 
Create Date: 2026-05-11 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001_create_qc_scheduler'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # extension for gen_random_uuid()
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto;')

    # enums
        # Create enums with idempotent checks to avoid duplicate-type race conditions
        op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'material_type') THEN
                CREATE TYPE material_type AS ENUM ('FG','RM','PM','Stability','IPQC','Micro');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'role_enum') THEN
                CREATE TYPE role_enum AS ENUM ('planner','admin','qa_viewer');
            END IF;
        END$$;
        """)

        # Referencing SQLAlchemy enum objects for table column definitions
        material_type = postgresql.ENUM('FG','RM','PM','Stability','IPQC','Micro', name='material_type')
        role_enum = postgresql.ENUM('planner','admin','qa_viewer', name='role_enum')

    # users
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('username', sa.Text(), nullable=False, unique=True),
        sa.Column('display_name', sa.Text()),
        sa.Column('email', sa.Text(), unique=True),
        sa.Column('role', role_enum, nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('totp_secret', sa.Text()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'))
    )

    op.create_table(
        'sections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.Text(), nullable=False)
    )

    op.create_table(
        'analysts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), unique=True),
        sa.Column('section_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sections.id')),
        sa.Column('active', sa.Boolean(), server_default=sa.text('true'))
    )

    op.create_table(
        'instruments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('type', sa.Text(), nullable=False),
        sa.Column('model', sa.Text()),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('last_calibrated', sa.TIMESTAMP(timezone=True)),
        sa.Column('next_calibration_due', sa.TIMESTAMP(timezone=True)),
        sa.Column('protected_time', sa.JSON(), server_default=sa.text("'[]'::jsonb"))
    )

    op.create_table(
        'methods',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('code', sa.Text(), nullable=False, unique=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('steps', sa.JSON(), nullable=False),
        sa.Column('estimated_active_minutes', sa.Integer(), nullable=False)
    )

    op.create_table(
        'analyst_qualifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('analyst_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analysts.id', ondelete='CASCADE')),
        sa.Column('method_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('methods.id', ondelete='CASCADE')),
        sa.Column('instrument_type', sa.Text(), nullable=False),
        sa.UniqueConstraint('analyst_id', 'method_id', 'instrument_type', name='uq_analyst_method_instrument')
    )

    op.create_table(
        'shifts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.Text()),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False)
    )

    op.create_table(
        'analyst_shifts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('analyst_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analysts.id')),
        sa.Column('shift_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('shifts.id')),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date())
    )

    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('sample_id', sa.Text(), nullable=False),
        sa.Column('method_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('methods.id'), nullable=False),
        sa.Column('material', material_type, nullable=False),
        sa.Column('quantity', sa.Integer(), server_default='1'),
        sa.Column('sla_date', sa.TIMESTAMP(timezone=True)),
        sa.Column('supply_chain_priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ipqc_status', sa.Text()),
        sa.Column('campaign_group_key', sa.Text()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
        sa.Column('requested_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.CheckConstraint('supply_chain_priority >= 0 AND supply_chain_priority <= 10', name='ck_supply_chain_priority_range')
    )

    op.create_table(
        'scheduled_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs.id'), nullable=False),
        sa.Column('method_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('methods.id'), nullable=False),
        sa.Column('analyst_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analysts.id'), nullable=False),
        sa.Column('instrument_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('instruments.id'), nullable=False),
        sa.Column('start_time', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('end_time', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('step', sa.JSON()),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'))
    )

    op.create_table(
        'blocked_slots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('scheduled_task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('scheduled_tasks.id', ondelete='CASCADE')),
        sa.Column('blocked_start', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('blocked_end', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('reason', sa.Text())
    )

    op.create_table(
        'audit_log',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()')),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('target_type', sa.Text()),
        sa.Column('target_id', postgresql.UUID(as_uuid=True)),
        sa.Column('payload', sa.JSON()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
        sa.Column('prev_hash', sa.Text()),
        sa.Column('hash', sa.Text(), nullable=False)
    )

    # Indexes
    op.create_index('idx_jobs_sla', 'jobs', ['sla_date'])
    op.create_index('idx_scheduled_tasks_range', 'scheduled_tasks', ['start_time', 'end_time'])
    op.create_index('idx_instruments_type_status', 'instruments', ['type', 'status'])

    # Make audit_log immutable at DB layer: prevent UPDATE/DELETE on audit_log
    op.execute("""
    CREATE FUNCTION audit_log_prevent_modifications() RETURNS trigger AS $$
    BEGIN
      RAISE EXCEPTION 'audit_log is immutable';
      RETURN NULL;
    END;
    $$ LANGUAGE plpgsql;
    """)
    op.execute("""
    CREATE TRIGGER trg_audit_log_immutable
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_prevent_modifications();
    """)


def downgrade():
    # Drop trigger and function
    op.execute('DROP TRIGGER IF EXISTS trg_audit_log_immutable ON audit_log;')
    op.execute('DROP FUNCTION IF EXISTS audit_log_prevent_modifications();')

    # Drop indexes
    op.drop_index('idx_instruments_type_status', table_name='instruments')
    op.drop_index('idx_scheduled_tasks_range', table_name='scheduled_tasks')
    op.drop_index('idx_jobs_sla', table_name='jobs')

    # Drop tables
    op.drop_table('audit_log')
    op.drop_table('blocked_slots')
    op.drop_table('scheduled_tasks')
    op.drop_table('jobs')
    op.drop_table('analyst_shifts')
    op.drop_table('shifts')
    op.drop_table('analyst_qualifications')
    op.drop_table('methods')
    op.drop_table('instruments')
    op.drop_table('analysts')
    op.drop_table('sections')
    op.drop_table('users')

    # Drop enums
    material_type = postgresql.ENUM('FG','RM','PM','Stability','IPQC','Micro', name='material_type')
    material_type.drop(op.get_bind(), checkfirst=True)

    role_enum = postgresql.ENUM('planner','admin','qa_viewer', name='role_enum')
    role_enum.drop(op.get_bind(), checkfirst=True)
