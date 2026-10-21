"""
Event and trigger models.
"""
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class Event(BaseModel):
    event_id: str
    viewer_id: str
    event_type: str # app_open, sign_up, play, search, page_view, purchase, message_delivery, message_click
    timestamp: datetime
    received_at: datetime
    event_age_s: float = 0.0
    payload: Dict[str, Any] = Field(default_factory=dict)

    def calculate_age(self) -> float:
        delta = (self.received_at - self.timestamp).total_seconds()
        self.event_age_s = max(0.0, round(delta, 2))
        return self.event_age_s

class TriggerInfo(BaseModel):
    event: str
    received_at: str
    event_age_s: float
