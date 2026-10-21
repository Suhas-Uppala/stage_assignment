"""
ViewerAgent: Logical per-viewer agent owning state, history, and single active goal.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from src.models import Event, ViewerState, ActiveGoal
from src.storage.state_store import StateStore

class ViewerAgent:
    def __init__(self, viewer_id: str, state_store: StateStore):
        self.viewer_id = viewer_id
        self.state_store = state_store
        self.state = self.state_store.get_viewer_state(viewer_id)

    def refresh(self):
        self.state = self.state_store.get_viewer_state(self.viewer_id)

    def save(self):
        self.state_store.save_viewer_state(self.state)

    def process_incoming_event(self, event: Event):
        self.state.last_event_time = event.timestamp
        self.state.last_seen_event_id = event.event_id

        if event.event_type == "play":
            t_id = event.payload.get("title_id")
            if t_id and t_id not in self.state.watched_titles:
                self.state.watched_titles.append(t_id)
            
            # Check completion
            pct = float(event.payload.get("progress_pct", 0.0))
            completed = bool(event.payload.get("completed", False)) or (pct >= 85.0)
            if completed:
                self.state.completed_episodes += 1

        elif event.event_type == "purchase":
            if event.payload.get("status") == "success":
                from src.models import ViewerFact
                self.state.facts["subscription_status"] = ViewerFact(
                    fact_key="subscription_status",
                    value="paid",
                    source="event_stream",
                    recorded_at=event.timestamp,
                    freshness_s=0.0
                )
                # If an active goal was conversion (e.g. first_paid_plan_7d), mark succeeded
                if self.state.active_goal and "paid_plan" in self.state.active_goal.goal_id:
                    self.state.active_goal.status = "SUCCEEDED"

        self.save()

    def record_message_sent(self, sent_time: datetime):
        day_str = sent_time.strftime("%Y-%m-%d")
        current_cnt = self.state.daily_messages_sent.get(day_str, 0)
        self.state.daily_messages_sent[day_str] = current_cnt + 1
        self.save()

    def get_messages_sent_today(self, current_time: datetime) -> int:
        day_str = current_time.strftime("%Y-%m-%d")
        return self.state.daily_messages_sent.get(day_str, 0)
