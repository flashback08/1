from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from typing import List
import json
from app.db import get_db
from app.schemas import PlanRequest, ReplanRequest, UpdateTaskRequest, PlannerDayResponse
from app.scheduler import schedule_daily_plan, replan_min_mod
from db.models import User, Section, Analyst, Instrument, Method, AnalystQualification, Shift, AnalystShift, Job
from sqlalchemy.orm import Session
from uuid import UUID

router = APIRouter()

@router.get('/planner/day', response_model=PlannerDayResponse)
def planner_day(date: str, db=Depends(get_db)):
    plan = schedule_daily_plan(date, db)
    return plan

@router.post('/schedule/plan')
def plan_endpoint(req: PlanRequest, db=Depends(get_db)):
    options = req.options.dict() if req.options else {}
    plan = schedule_daily_plan(req.date, db, options)
    return plan

@router.post('/schedule/replan')
def replan_endpoint(req: ReplanRequest, db=Depends(get_db)):
    plan = replan_min_mod(req.new_jobs, db, req.current_schedule)
    return plan

@router.patch('/schedule/task/{task_id}')
def update_task(task_id: str, payload: UpdateTaskRequest, db=Depends(get_db)):
    # Minimal validation: in production validate qualifications, instrument availability and write audit entry
    # Here we simply return the attempted update
    return {
        'status': 'ok',
        'task_id': task_id,
        'updated': payload.dict()
    }

@router.get('/audit')
def get_audit(limit: int = 100, db=Depends(get_db)):
    # Minimal: query audit_log table if present
    try:
        rows = db.execute('SELECT event_id, actor_id, action, created_at FROM audit_log ORDER BY created_at DESC LIMIT :l', {'l': limit}).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        raise HTTPException(status_code=500, detail='Audit log not available')

@router.post('/upload/dummy-data')
async def upload_dummy_data(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload a JSON file containing dummy data (users, sections, analysts, instruments, methods, etc.)
    and populate the database with it.
    """
    try:
        contents = await file.read()
        data = json.loads(contents.decode('utf-8'))
        
        # Clear existing data (optional; for demo purposes)
        # db.query(Job).delete()
        # db.query(AnalystShift).delete()
        # db.query(Shift).delete()
        # db.commit()
        
        # Load users
        for user_data in data.get('users', []):
            user = User(
                id=UUID(user_data['id']),
                username=user_data['username'],
                display_name=user_data.get('display_name'),
                email=user_data.get('email'),
                role=user_data['role'],
                password_hash=user_data.get('password_hash', 'demo_hash'),
                totp_secret=user_data.get('totp_secret')
            )
            db.merge(user)
        
        # Load sections
        for section_data in data.get('sections', []):
            section = Section(
                id=UUID(section_data['id']),
                name=section_data['name']
            )
            db.merge(section)
        
        # Load analysts
        for analyst_data in data.get('analysts', []):
            analyst = Analyst(
                id=UUID(analyst_data['id']),
                user_id=UUID(analyst_data['user_id']) if analyst_data.get('user_id') else None,
                section_id=UUID(analyst_data['section_id']) if analyst_data.get('section_id') else None,
                active=analyst_data.get('active', True)
            )
            db.merge(analyst)
        
        # Load instruments
        for instr_data in data.get('instruments', []):
            instrument = Instrument(
                id=UUID(instr_data['id']),
                name=instr_data['name'],
                type=instr_data['type'],
                model=instr_data.get('model'),
                status=instr_data.get('status', 'available'),
                last_calibrated=instr_data.get('last_calibrated'),
                next_calibration_due=instr_data.get('next_calibration_due'),
                protected_time=instr_data.get('protected_time', [])
            )
            db.merge(instrument)
        
        # Load methods
        for method_data in data.get('methods', []):
            method = Method(
                id=UUID(method_data['id']),
                code=method_data['code'],
                name=method_data['name'],
                steps=method_data.get('steps', []),
                estimated_active_minutes=method_data.get('estimated_active_minutes', 0)
            )
            db.merge(method)
        
        # Load analyst qualifications
        for qual_data in data.get('analyst_qualifications', []):
            qual = AnalystQualification(
                id=UUID(qual_data['id']),
                analyst_id=UUID(qual_data['analyst_id']),
                method_id=UUID(qual_data['method_id']),
                instrument_type=qual_data['instrument_type']
            )
            db.merge(qual)
        
        # Load shifts
        for shift_data in data.get('shifts', []):
            shift = Shift(
                id=UUID(shift_data['id']),
                name=shift_data.get('name'),
                start_time=shift_data.get('start_time'),
                end_time=shift_data.get('end_time')
            )
            db.merge(shift)
        
        # Load analyst shifts
        for ashift_data in data.get('analyst_shifts', []):
            ashift = AnalystShift(
                id=UUID(ashift_data['id']),
                analyst_id=UUID(ashift_data['analyst_id']),
                shift_id=UUID(ashift_data['shift_id']),
                start_date=ashift_data.get('start_date'),
                end_date=ashift_data.get('end_date')
            )
            db.merge(ashift)
        
        # Load jobs
        for job_data in data.get('jobs', []):
            job = Job(
                id=UUID(job_data['id']),
                sample_id=job_data['sample_id'],
                method_id=UUID(job_data['method_id']),
                material=job_data.get('material', 'FG'),
                quantity=job_data.get('quantity', 1),
                sla_date=job_data.get('sla_date'),
                supply_chain_priority=job_data.get('supply_chain_priority', 0),
                ipqc_status=job_data.get('ipqc_status'),
                campaign_group_key=job_data.get('campaign_group_key'),
                requested_by=UUID(job_data['requested_by']) if job_data.get('requested_by') else None
            )
            db.merge(job)
        
        db.commit()
        return {
            'status': 'success',
            'message': 'Dummy data loaded successfully',
            'records_loaded': {
                'users': len(data.get('users', [])),
                'sections': len(data.get('sections', [])),
                'analysts': len(data.get('analysts', [])),
                'instruments': len(data.get('instruments', [])),
                'methods': len(data.get('methods', [])),
                'analyst_qualifications': len(data.get('analyst_qualifications', [])),
                'shifts': len(data.get('shifts', [])),
                'analyst_shifts': len(data.get('analyst_shifts', [])),
                'jobs': len(data.get('jobs', []))
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f'Error loading dummy data: {str(e)}')
