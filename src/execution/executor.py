"""
Action executor: safe execution, idempotency, side-effect isolation, and status tracking.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from src.models import ActionRecord, ChecksResult
from src.state.viewer_agent import ViewerAgent
from src.storage.state_store import StateStore

class ActionExecutor:
    def __init__(self, state_store: StateStore):
        self.state_store = state_store

    def execute(
        self,
        decision_id: str,
        viewer_id: str,
        action_type: str,
        content_refs: List[str],
        is_verified: bool,
        checks: ChecksResult,
        idempotency_key: str,
        eval_time: datetime,
        viewer_agent: ViewerAgent,
        rejection_reason: Optional[str] = None
    ) -> ActionRecord:
        # Check idempotency first
        existing_actions = [a for a in self.state_store.get_all_actions() if a.idempotency_key == idempotency_key]
        if existing_actions:
            return existing_actions[0]

        channel_map = {
            "HOME_PAGE": "in_app",
            "HERO_SLOT": "in_app",
            "IN_APP_MESSAGE": "in_app",
            "PUSH_NOTIFICATION": "push",
            "WHATSAPP": "whatsapp",
            "NO_ACTION": "none"
        }
        channel = channel_map.get(action_type, "none")

        action_id = f"ACT-{uuid.uuid4().hex[:8].upper()}"

        # Determine execution status
        if not is_verified:
            status = "BLOCKED"
        elif action_type == "NO_ACTION":
            status = "NO_ACTION"
        else:
            status = "PUBLISHED"
            # Apply side effects
            if action_type in ["PUSH_NOTIFICATION", "WHATSAPP"]:
                viewer_agent.record_message_sent(eval_time)

        record = ActionRecord(
            action_id=action_id,
            decision_id=decision_id,
            viewer_id=viewer_id,
            action_type=action_type,
            channel=channel,
            content=content_refs,
            executed_at=eval_time,
            status=status,
            idempotency_key=idempotency_key,
            details={
                "checks_passed": checks.passed,
                "checks_failed": checks.failed,
                "rejection_reason": rejection_reason
            }
        )

        self.state_store.record_action(record)
        return record
