from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class PlanOptions(BaseModel):
    mode: Optional[str] = 'greedy'  # or 'ilp'
    max_days: Optional[int] = 1

class PlanRequest(BaseModel):
    date: str
    options: Optional[PlanOptions] = None

class ReplanRequest(BaseModel):
    new_jobs: List[Dict[str, Any]]
    current_schedule: Optional[Dict[str, Any]] = None

class UpdateTaskRequest(BaseModel):
    start_time: str
    end_time: str
    reason: Optional[str] = None

class ScheduledTask(BaseModel):
    id: str
    job_id: str
    method_id: str
    analyst_id: str
    instrument_id: str
    start_time: str
    end_time: str
    status: str

class PlannerDayResponse(BaseModel):
    date: str
    scheduled: List[ScheduledTask] = []
    unassigned: List[Dict[str, Any]] = []
