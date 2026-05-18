from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date as datecls, time as timecls, timedelta
import math
import hashlib
import json

from db.models import Job, Method, Analyst, Instrument, AnalystQualification, ScheduledTask, BlockedSlot, Method as MethodModel, AuditLog


def _get_last_hash(session) -> str:
    last = session.query(AuditLog).order_by(AuditLog.id.desc()).limit(1).first()
    return last.hash if last and last.hash else ''


def _write_audit(session, actor_id: Optional[str], action: str, target_type: str, target_id: str, payload: Dict[str, Any]):
    # Compute chained hash and insert audit_log row (flush only; commit done by caller)
    prev_hash = _get_last_hash(session) or ''
    created_at = datetime.utcnow()
    payload_json = json.dumps(payload, sort_keys=True, default=str)
    actor_part = str(actor_id) if actor_id else ''
    hash_input = prev_hash + actor_part + action + target_type + target_id + payload_json + created_at.isoformat()
    new_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
    audit = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        payload=payload,
        created_at=created_at,
        prev_hash=prev_hash,
        hash=new_hash
    )
    session.add(audit)
    session.flush()
    return audit


SLOT_INCREMENT_MINUTES = 15
DAY_START = timecls(hour=8, minute=0)
DAY_END = timecls(hour=18, minute=0)


def _parse_date(d: str) -> datecls:
    return datetime.strptime(d, '%Y-%m-%d').date()


def _datetime_from_date_and_time(d: datecls, t: timecls) -> datetime:
    return datetime.combine(d, t)


def _overlaps(session, analyst_id: Optional[str], instrument_id: Optional[str], start: datetime, end: datetime) -> bool:
    # Return True if analyst or instrument has scheduled task overlapping start/end
    q = session.query(ScheduledTask).filter(
        ScheduledTask.start_time < end,
        ScheduledTask.end_time > start,
    )
    if analyst_id:
        q = q.filter(ScheduledTask.analyst_id == analyst_id)
    if instrument_id:
        q = q.filter(ScheduledTask.instrument_id == instrument_id)
    return session.query(q.exists()).scalar()


def _instrument_protected(instrument: Instrument, dt_start: datetime, dt_end: datetime) -> bool:
    # protected_time stored as list of {dow:1..7, start:'HH:MM', end:'HH:MM'}
    try:
        blocks = instrument.protected_time or []
    except Exception:
        blocks = []
    for b in blocks:
        dow = int(b.get('dow'))  # 1..7 (Monday=1)
        start_str = b.get('start')
        end_str = b.get('end')
        if not start_str or not end_str:
            continue
        block_start = datetime.combine(dt_start.date(), datetime.strptime(start_str, '%H:%M').time())
        block_end = datetime.combine(dt_start.date(), datetime.strptime(end_str, '%H:%M').time())
        # adjust dow
        if dt_start.isoweekday() == dow or dt_end.isoweekday() == dow:
            if block_start < dt_end and block_end > dt_start:
                return True
    return False


def _find_earliest_slot(session, analyst_id: str, instrument: Instrument, plan_date: datecls, duration_minutes: int) -> Optional[Tuple[datetime, datetime]]:
    # Scan from DAY_START to DAY_END in SLOT_INCREMENT_MINUTES increments
    duration = timedelta(minutes=duration_minutes)
    slot = _datetime_from_date_and_time(plan_date, DAY_START)
    end_of_day = _datetime_from_date_and_time(plan_date, DAY_END)
    while slot + duration <= end_of_day:
        candidate_start = slot
        candidate_end = slot + duration
        # check analyst and instrument overlaps
        if _overlaps(session, analyst_id, instrument.id, candidate_start, candidate_end):
            slot += timedelta(minutes=SLOT_INCREMENT_MINUTES)
            continue
        # check instrument protected time
        if _instrument_protected(instrument, candidate_start, candidate_end):
            slot += timedelta(minutes=SLOT_INCREMENT_MINUTES)
            continue
        return candidate_start, candidate_end
    return None


def _compute_priority(job_row: Job, reference_date: datetime) -> float:
    # SLA urgency: inverse days to SLA (more urgent -> higher). Supply chain priority scaled. IPQC gives bonus.
    sla_score = 0.0
    if job_row.sla_date:
        days = (job_row.sla_date - reference_date).total_seconds() / 86400.0
        # if overdue or due soon, produce larger score
        if days <= 0:
            sla_score = 100.0
        else:
            sla_score = max(0.0, 10.0 / days)
    supply_score = float(job_row.supply_chain_priority or 0)
    ipqc_score = 0.0
    if job_row.ipqc_status and job_row.ipqc_status.lower() in ('critical','hold'):
        ipqc_score = 20.0
    return sla_score + supply_score + ipqc_score


def _extract_steps(method_row: MethodModel) -> List[Dict[str, Any]]:
    # Expect method_row.steps to be a list of dicts with keys: step, active_minutes, wait_days
    try:
        steps = method_row.steps or []
    except Exception:
        steps = []
    # normalize
    normalized = []
    for s in steps:
        normalized.append({
            'step': s.get('step'),
            'active_minutes': int(s.get('active_minutes', 0)) if s.get('active_minutes') is not None else 0,
            'wait_days': int(s.get('wait_days', 0)) if s.get('wait_days') is not None else 0
        })
    return normalized


def schedule_daily_plan(date: str, db, options: Dict[str, Any] = None) -> Dict[str, Any]:
    """Greedy campaign-aware scheduler.

    By default this function does not persist changes unless `options['persist']==True`.
    """
    plan_date = _parse_date(date)
    now = datetime.utcnow()
    reference_dt = datetime.combine(plan_date, DAY_START)

    # Load data
    jobs = db.query(Job).all()
    methods = {m.id: m for m in db.query(Method).all()}
    analysts = {a.id: a for a in db.query(Analyst).filter(Analyst.active == True).all()}
    instruments = {i.id: i for i in db.query(Instrument).filter(Instrument.status == 'available').all()}

    # Group campaigns
    campaign_groups: Dict[str, List[Job]] = {}
    non_campaign_jobs: List[Job] = []
    for j in jobs:
        if j.campaign_group_key:
            key = f"{j.campaign_group_key}::{j.method_id}"
            campaign_groups.setdefault(key, []).append(j)
        else:
            non_campaign_jobs.append(j)

    # compute priorities
    job_priority = {}
    for j in jobs:
        job_priority[j.id] = _compute_priority(j, reference_dt)

    scheduled_output = []
    unassigned = []

    def _assign_step(job_obj: Job, method_obj: MethodModel, step_idx: int, step_def: Dict[str, Any], assigned_analyst_id: Optional[str] = None, assigned_instrument_id: Optional[str] = None, preferred_start: Optional[datetime] = None):
        duration = int(step_def.get('active_minutes', 0))
        if duration <= 0:
            return None
        # find candidate analyst/instrument pairs
        candidate_pairs = []
        for a in analysts.values():
            # check qualification for method + instrument types will be checked per instrument
            quals = db.query(AnalystQualification).filter(AnalystQualification.analyst_id == a.id, AnalystQualification.method_id == method_obj.id).all()
            if not quals:
                continue
            for inst in instruments.values():
                # instrument type must be in quals
                types = [q.instrument_type for q in quals]
                if inst.type not in types:
                    continue
                candidate_pairs.append((a, inst))

        # sort candidates by minimal existing load (count of scheduled tasks for day)
        def load_score(pair):
            a, inst = pair
            cnt = db.query(ScheduledTask).filter(ScheduledTask.analyst_id == a.id, ScheduledTask.start_time >= reference_dt, ScheduledTask.start_time < reference_dt + timedelta(days=1)).count()
            cnt += db.query(ScheduledTask).filter(ScheduledTask.instrument_id == inst.id, ScheduledTask.start_time >= reference_dt, ScheduledTask.start_time < reference_dt + timedelta(days=1)).count()
            return cnt

        candidate_pairs.sort(key=load_score)

        assigned = None
        for a, inst in candidate_pairs:
            slot = _find_earliest_slot(db, a.id, inst, plan_date, duration)
            if not slot:
                continue
            start_time, end_time = slot
            # if preferred_start set, ensure we pick slot at or after it
            if preferred_start and start_time < preferred_start:
                # try to move to preferred_start by verifying overlap
                candidate_start = preferred_start
                candidate_end = preferred_start + timedelta(minutes=duration)
                if candidate_end.time() > DAY_END:
                    continue
                if _overlaps(db, a.id, inst.id, candidate_start, candidate_end):
                    continue
                if _instrument_protected(inst, candidate_start, candidate_end):
                    continue
                start_time, end_time = candidate_start, candidate_end

            # If here, assign
            task = {
                'job_id': str(job_obj.id),
                'method_id': str(method_obj.id),
                'analyst_id': str(a.id),
                'instrument_id': str(inst.id),
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'step': step_def.get('step'),
                'status': 'planned'
            }
            assigned = (task, a, inst, start_time, end_time)
            break

        if not assigned:
            return None

        task, a, inst, start_time, end_time = assigned
        # Optionally persist
        if options and options.get('persist'):
            st = ScheduledTask(
                job_id=job_obj.id,
                method_id=method_obj.id,
                analyst_id=a.id,
                instrument_id=inst.id,
                start_time=start_time,
                end_time=end_time,
                step={'step': step_def.get('step')},
                status='planned'
            )
            db.add(st)
            db.flush()  # get id
            assigned_task_id = st.id

            # audit entry for created scheduled task
            actor_id = None
            if options and options.get('actor_id'):
                actor_id = options.get('actor_id')
            payload = {
                'job_id': str(job_obj.id),
                'method_id': str(method_obj.id),
                'analyst_id': str(a.id),
                'instrument_id': str(inst.id),
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'step': step_def.get('step')
            }
            _write_audit(db, actor_id, 'create_scheduled_task', 'scheduled_task', str(st.id), payload)

            # create blocked slots for subsequent wait points in the method steps
            # any step after this one that has wait_days creates a callback slot
            subsequent = method_obj.steps[step_idx+1:] if method_obj.steps else []
            for sub in subsequent:
                wait_days = int(sub.get('wait_days', 0)) if sub.get('wait_days') is not None else 0
                if wait_days and wait_days > 0:
                    blocked_start = end_time + timedelta(days=wait_days)
                    blocked_end = blocked_start + timedelta(hours=1)  # reserve 1 hour for callback
                    bs = BlockedSlot(
                        scheduled_task_id=st.id,
                        blocked_start=blocked_start,
                        blocked_end=blocked_end,
                        reason=f"callback:{sub.get('step')}"
                    )
                    db.add(bs)
                    db.flush()
                    _write_audit(db, actor_id, 'create_blocked_slot', 'blocked_slot', str(bs.id), {
                        'scheduled_task_id': str(st.id),
                        'blocked_start': blocked_start.isoformat(),
                        'blocked_end': blocked_end.isoformat(),
                        'reason': bs.reason
                    })
        else:
            assigned_task_id = None

        scheduled_output.append(task)
        return assigned

    # First schedule campaign groups
    campaign_items = list(campaign_groups.items())
    # sort by max job priority in group and earliest SLA
    def group_sort_key(item):
        key, jobs_list = item
        maxp = max(job_priority[j.id] for j in jobs_list)
        earliest_sla = min((j.sla_date or reference_dt) for j in jobs_list)
        return (-maxp, earliest_sla)

    for key, jobs_list in sorted(campaign_items, key=group_sort_key):
        # all jobs share same method_id via grouping key format
        method_id = jobs_list[0].method_id
        method_obj = methods.get(method_id)
        if not method_obj:
            for j in jobs_list:
                unassigned.append({'job_id': str(j.id), 'reason': 'method_not_found'})
            continue
        steps = _extract_steps(method_obj)
        # schedule shared prep step if exists
        prep_steps = [s for s in steps if s.get('step') and 'prep' in s.get('step').lower()]
        if prep_steps:
            prep = prep_steps[0]
            # create a single prep task for the group
            # pick one job as representative for job_id linking
            rep_job = jobs_list[0]
            assigned = _assign_step(rep_job, method_obj, 0, prep)
            if not assigned:
                for j in jobs_list:
                    unassigned.append({'job_id': str(j.id), 'reason': 'no_prep_slot'})
                continue
            # After prep, schedule each job's run/active steps (non-prep active steps)
            for j in jobs_list:
                for idx, s in enumerate(steps):
                    if s == prep:
                        continue
                    if s.get('active_minutes', 0) > 0:
                        _assign_step(j, method_obj, idx, s)
                    elif s.get('wait_days', 0) > 0:
                        # create blocked slot for future callback when persisting
                        if options and options.get('persist'):
                            # find last created scheduled task for job to link
                            pass
        else:
            # No shared prep, schedule each job normally
            for j in jobs_list:
                for idx, s in enumerate(steps):
                    if s.get('active_minutes', 0) > 0:
                        _assign_step(j, method_obj, idx, s)
                    elif s.get('wait_days', 0) > 0:
                        # will create blocked slots when persisting
                        pass

    # Then schedule non-campaign jobs by priority
    remaining = sorted(non_campaign_jobs, key=lambda j: (-job_priority[j.id], j.sla_date or reference_dt))
    for j in remaining:
        method_obj = methods.get(j.method_id)
        if not method_obj:
            unassigned.append({'job_id': str(j.id), 'reason': 'method_not_found'})
            continue
        steps = _extract_steps(method_obj)
        for idx, s in enumerate(steps):
            if s.get('active_minutes', 0) > 0:
                assigned = _assign_step(j, method_obj, idx, s)
                if not assigned:
                    unassigned.append({'job_id': str(j.id), 'reason': 'no_slot_for_step', 'step': s.get('step')})
            elif s.get('wait_days', 0) > 0:
                # multi-day wait; when persist==True we'll create blocked_slots linking to prior scheduled task
                pass

    # If persist requested, commit DB changes and create blocked_slots for wait points
    if options and options.get('persist'):
        # commit created scheduled tasks
        db.commit()
        # Note: creating blocked_slots requires mapping tasks to jobs/steps; omitted in this minimal impl

    return {
        'date': date,
        'scheduled': scheduled_output,
        'unassigned': unassigned
    }


def replan_min_mod(new_jobs: List[Dict[str, Any]], db, current_schedule: Dict[str, Any] = None) -> Dict[str, Any]:
    # Very small min-mod heuristic: try to insert into day using schedule_daily_plan with transient persistence
    # Attempt non-persist run first to see where new jobs would fit.
    today = datetime.utcnow().date().isoformat()
    plan = schedule_daily_plan(today, db, options={'persist': False})
    # naive: append new jobs to plan using same logic
    scheduled = []
    for j in new_jobs:
        scheduled.append({
            'id': j.get('id') or f"tmp-{j.get('sample_id')}",
            'job_id': j.get('id') or j.get('sample_id'),
            'method_id': j.get('method_id'),
            'analyst_id': None,
            'instrument_id': None,
            'start_time': j.get('requested_start'),
            'end_time': j.get('requested_end'),
            'status': 'pending'
        })
    return {'scheduled': scheduled, 'unassigned': []}
