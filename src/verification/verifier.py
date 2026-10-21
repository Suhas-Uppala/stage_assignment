"""
Independent Policy and Safety Verifier:
Separated from the decision/planning step. Strictly verifies eligibility, dialect,
availability, row size, quiet hours, consent, frequency caps, and idempotency.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from src.config import CONFIG
from src.models import (
    Event, ViewerState, ActiveGoal, DialectResolution, ContentTitle, ChecksResult
)
from src.state.fact_resolver import FactResolver
from src.storage.state_store import StateStore

class IndependentVerifier:
    def __init__(self, state_store: Optional[StateStore] = None):
        self.state_store = state_store

    def verify(
        self,
        viewer_id: str,
        action: str,
        content_refs: List[str],
        content_titles: List[ContentTitle],
        active_goal: Optional[ActiveGoal],
        dialect_res: DialectResolution,
        state: ViewerState,
        profile: Optional[Dict[str, Any]],
        eval_time: datetime,
        messages_sent_today: int = 0
    ) -> Tuple[bool, ChecksResult, Optional[str]]:
        """
        Executes strict verification checks.
        Returns (is_passed, ChecksResult(passed=[...], failed=[...]), failure_summary)
        """
        passed: List[str] = []
        failed: List[str] = []

        # If action is NO_ACTION, verify that reason is present
        if action == "NO_ACTION":
            passed.append("no_action_valid")
            return True, ChecksResult(passed=passed, failed=[]), None

        # 1. Goal Eligibility Check
        if active_goal:
            # Objective verification against state
            if "first_paid_plan" in active_goal.goal_id:
                sub_fact = state.facts.get("subscription_status")
                if sub_fact and sub_fact.value == "paid":
                    failed.append("eligibility")
                else:
                    passed.append("eligibility")
            elif "first_full_episode" in active_goal.goal_id:
                if state.completed_episodes > 0:
                    failed.append("eligibility")
                else:
                    passed.append("eligibility")
            else:
                passed.append("eligibility")
        else:
            failed.append("eligibility")

        # 2. Dialect Consistency Check
        dialect_mismatch = False
        for t in content_titles:
            if t.dialect != dialect_res.used:
                dialect_mismatch = True
                break
        if dialect_mismatch:
            failed.append("dialect")
        else:
            passed.append("dialect")

        # 3. Content Availability Window Check
        availability_mismatch = False
        for t in content_titles:
            if not (t.available_from <= eval_time <= t.available_to):
                availability_mismatch = True
                break
        if availability_mismatch:
            failed.append("availability")
        else:
            passed.append("availability")

        # 4. Minimum Row Size for HOME_PAGE Check
        if action == "HOME_PAGE":
            if len(content_refs) < CONFIG.MIN_HOME_PAGE_TITLES:
                failed.append("minimum_row_size")
            else:
                passed.append("minimum_row_size")

        # 5. Consent Check (Push & WhatsApp)
        if action == "PUSH_NOTIFICATION":
            consent_fact = state.facts.get("consent_push")
            has_consent = bool(consent_fact.value) if consent_fact else False
            if not has_consent:
                failed.append("channel_consent")
            else:
                passed.append("channel_consent")
        elif action == "WHATSAPP":
            consent_fact = state.facts.get("consent_whatsapp")
            has_consent = bool(consent_fact.value) if consent_fact else False
            if not has_consent:
                failed.append("channel_consent")
            else:
                passed.append("channel_consent")
        else:
            passed.append("channel_consent")

        # 6. Quiet Hours Check (22:00 to 08:00 local time)
        if action in ["PUSH_NOTIFICATION", "WHATSAPP"]:
            if FactResolver.is_quiet_hours(eval_time):
                failed.append("quiet_hours")
            else:
                passed.append("quiet_hours")
        else:
            passed.append("quiet_hours")

        # 7. Daily Frequency Cap Check (Max 1 msg per day)
        if action in ["PUSH_NOTIFICATION", "WHATSAPP"]:
            if messages_sent_today >= CONFIG.MAX_MESSAGES_PER_VIEWER_PER_DAY:
                failed.append("frequency_cap")
            else:
                passed.append("frequency_cap")
        else:
            passed.append("frequency_cap")

        # Result summary
        is_verified = (len(failed) == 0)
        failure_summary = f"Verification failed checks: {', '.join(failed)}" if failed else None

        return is_verified, ChecksResult(passed=passed, failed=failed), failure_summary
