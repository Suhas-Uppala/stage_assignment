"""
Viewer state, facts with provenance, and active goal models.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ViewerFact(BaseModel):
    fact_key: str
    value: Any
    source: str # app_setting, profile_snapshot, event_stream, campaign_link
    recorded_at: datetime
    freshness_s: float = 0.0
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)

class ActiveGoal(BaseModel):
    goal_id: str
    name: str
    version: str
    selected_at: datetime
    deadline: datetime
    success_signal: str
    target_metric: str
    evidence_ids: List[str] = Field(default_factory=list)
    status: str = "ACTIVE" # ACTIVE, SUCCEEDED, FAILED, SUPERSEDED, INCONCLUSIVE

class ViewerState(BaseModel):
    viewer_id: str
    facts: Dict[str, ViewerFact] = Field(default_factory=dict)
    active_goal: Optional[ActiveGoal] = None
    goal_history: List[ActiveGoal] = Field(default_factory=list)
    watched_titles: List[str] = Field(default_factory=list)
    completed_episodes: int = 0
    daily_messages_sent: Dict[str, int] = Field(default_factory=dict) # YYYY-MM-DD -> count
    last_event_time: Optional[datetime] = None
    last_seen_event_id: Optional[str] = None
    version: int = 1
