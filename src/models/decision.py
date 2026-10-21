"""
Decision record schema strictly matching assignment requirements.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class DialectResolution(BaseModel):
    used: str
    source: str # app_setting, profile, campaign_link, default
    conflicts: List[str] = Field(default_factory=list)

class GoalDecisionRef(BaseModel):
    id: str
    deadline: str

class ChecksResult(BaseModel):
    passed: List[str] = Field(default_factory=list)
    failed: List[str] = Field(default_factory=list)

class DecisionRecord(BaseModel):
    decision_id: str
    viewer_id: str
    trigger: Dict[str, Any] # {"event": "app_open", "received_at": "...", "event_age_s": 9}
    goal: Optional[Dict[str, str]] = None # {"id": "first_full_episode_3d", "deadline": "..."}
    action: str # HOME_PAGE, HERO_SLOT, PUSH_NOTIFICATION, WHATSAPP, IN_APP_MESSAGE, NO_ACTION
    dialect: Dict[str, Any] # {"used": "d3", "source": "app_setting", "conflicts": ["profile:d1"]}
    content: List[str] = Field(default_factory=list)
    confidence: float
    confidence_reason: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    checks: Dict[str, List[str]] # {"passed": [...], "failed": [...]}
    decided_in_ms: float
    status: str # PUBLISHED, BLOCKED, NO_ACTION, FAILED
    reason: Optional[str] = None
    rule_version: Optional[str] = None
    idempotency_key: Optional[str] = None
