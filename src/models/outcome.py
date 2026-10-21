"""
Outcome and Action execution record models.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ActionRecord(BaseModel):
    action_id: str
    decision_id: str
    viewer_id: str
    action_type: str
    channel: str
    content: List[str]
    executed_at: datetime
    status: str # PUBLISHED, BLOCKED, NO_ACTION, FAILED
    idempotency_key: str
    details: Dict[str, Any] = Field(default_factory=dict)

class OutcomeRecord(BaseModel):
    outcome_id: str
    decision_id: str
    viewer_id: str
    goal_id: str
    goal_name: str
    rule_version: str
    classification: str # SUCCEEDED, FAILED, INCONCLUSIVE
    evaluated_at: datetime
    deadline: datetime
    qualifying_event_id: Optional[str] = None
    qualifying_event_time: Optional[datetime] = None
    reason: str
    evidence_ids: List[str] = Field(default_factory=list)
