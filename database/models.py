from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Time, ForeignKey,
    UniqueConstraint, CheckConstraint, JSON, Enum as SAEnum, text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()

class RoleEnum(str, enum.Enum):
    planner = 'planner'
    admin = 'admin'
    qa_viewer = 'qa_viewer'

class MaterialType(str, enum.Enum):
    FG = 'FG'
    RM = 'RM'
    PM = 'PM'
    Stability = 'Stability'
    IPQC = 'IPQC'
    Micro = 'Micro'

class User(Base):
    __tablename__ = 'users'
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    username = Column(String, nullable=False, unique=True)
    display_name = Column(String)
    email = Column(String, unique=True)
    role = Column(SAEnum(RoleEnum, name='role_enum'), nullable=False)
    password_hash = Column(String, nullable=False)
    totp_secret = Column(String)
    created_at = Column(DateTime, server_default=text('now()'))

class Section(Base):
    __tablename__ = 'sections'
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    name = Column(String, nullable=False)

class Analyst(Base):
    __tablename__ = 'analysts'
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), unique=True)
    section_id = Column(UUID(as_uuid=True), ForeignKey('sections.id'))
    active = Column(Boolean, default=True)

    user = relationship('User')
    section = relationship('Section')

class Instrument(Base):
    __tablename__ = 'instruments'
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    model = Column(String)
    status = Column(String, nullable=False)
    last_calibrated = Column(DateTime)
    next_calibration_due = Column(DateTime)
    protected_time = Column(JSON, server_default='[]')

class Method(Base):
    __tablename__ = 'methods'
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    steps = Column(JSON, nullable=False)
    estimated_active_minutes = Column(Integer, nullable=False)

class AnalystQualification(Base):
    __tablename__ = 'analyst_qualifications'
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    analyst_id = Column(UUID(as_uuid=True), ForeignKey('analysts.id', ondelete='CASCADE'))
    method_id = Column(UUID(as_uuid=True), ForeignKey('methods.id', ondelete='CASCADE'))
    instrument_type = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint('analyst_id', 'method_id', 'instrument_type', name='uq_analyst_method_instrument'),
    )

class Shift(Base):
    __tablename__ = 'shifts'
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    name = Column(String)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

class AnalystShift(Base):
    __tablename__ = 'analyst_shifts'
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    analyst_id = Column(UUID(as_uuid=True), ForeignKey('analysts.id'))
    shift_id = Column(UUID(as_uuid=True), ForeignKey('shifts.id'))
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime)

class Job(Base):
    __tablename__ = 'jobs'
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    sample_id = Column(String, nullable=False)
    method_id = Column(UUID(as_uuid=True), ForeignKey('methods.id'), nullable=False)
    material = Column(SAEnum(MaterialType, name='material_type'), nullable=False)
    quantity = Column(Integer, default=1)
    sla_date = Column(DateTime)
    supply_chain_priority = Column(Integer, nullable=False, default=0)
    ipqc_status = Column(String)
    campaign_group_key = Column(String)
    created_at = Column(DateTime, server_default=text('now()'))
    requested_by = Column(UUID(as_uuid=True), ForeignKey('users.id'))

    __table_args__ = (
        CheckConstraint('supply_chain_priority >= 0 AND supply_chain_priority <= 10', name='ck_supply_chain_priority_range'),
    )

class ScheduledTask(Base):
    __tablename__ = 'scheduled_tasks'
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    job_id = Column(UUID(as_uuid=True), ForeignKey('jobs.id'), nullable=False)
    method_id = Column(UUID(as_uuid=True), ForeignKey('methods.id'), nullable=False)
    analyst_id = Column(UUID(as_uuid=True), ForeignKey('analysts.id'), nullable=False)
    instrument_id = Column(UUID(as_uuid=True), ForeignKey('instruments.id'), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    step = Column(JSON)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=text('now()'))

class BlockedSlot(Base):
    __tablename__ = 'blocked_slots'
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    scheduled_task_id = Column(UUID(as_uuid=True), ForeignKey('scheduled_tasks.id', ondelete='CASCADE'))
    blocked_start = Column(DateTime, nullable=False)
    blocked_end = Column(DateTime, nullable=False)
    reason = Column(String)

class AuditLog(Base):
    __tablename__ = 'audit_log'
    id = Column(Integer, primary_key=True)
    event_id = Column(UUID(as_uuid=True), server_default=text('gen_random_uuid()'))
    actor_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    action = Column(String, nullable=False)
    target_type = Column(String)
    target_id = Column(UUID(as_uuid=True))
    payload = Column(JSON)
    created_at = Column(DateTime, server_default=text('now()'))
    prev_hash = Column(String)
    hash = Column(String, nullable=False)

# Note: Application should enforce immutability on AuditLog (no UPDATE/DELETE) and compute chained hash on insert.