"""
Catalogue models for content, goals, and interventions.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ContentTitle(BaseModel):
    title_id: str
    name: str
    dialect: str
    language: str
    genre: str
    episode_count: int
    episode_duration_mins: int
    available_from: datetime
    available_to: datetime
    description: str
    canonical_id: Optional[str] = None

class GoalDefinition(BaseModel):
    goal_id: str
    name: str
    version: str = "v1"
    description: str
    target_metric: str
    deadline_window_s: int
    eligibility: Dict[str, Any] = Field(default_factory=dict)
    success_conditions: Dict[str, Any] = Field(default_factory=dict)
    is_measurable: bool = True
    missing_signal: Optional[str] = None
    underspecified_note: Optional[str] = None

class InterventionTemplate(BaseModel):
    action_type: str # HOME_PAGE, HERO_SLOT, PUSH_NOTIFICATION, WHATSAPP, IN_APP_MESSAGE, NO_ACTION
    channel: str
    description: str
    constraints: Dict[str, Any] = Field(default_factory=dict)
