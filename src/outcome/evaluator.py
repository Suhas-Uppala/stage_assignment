"""
Outcome evaluator: classifies goals as SUCCEEDED, FAILED, or INCONCLUSIVE based on observable signals.
Supports rule versioning and targeted re-evaluation.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from src.models import DecisionRecord, Event, OutcomeRecord, ViewerState
from src.goals.rules import GoalRuleEngine
from src.storage.state_store import StateStore

class OutcomeEvaluator:
    def __init__(self, state_store: StateStore, rule_engine: Optional[GoalRuleEngine] = None):
        self.state_store = state_store
        self.rule_engine = rule_engine or GoalRuleEngine()

    def evaluate_decision_outcome(
        self,
        decision: DecisionRecord,
        events: List[Event],
        eval_time: datetime,
        rule_version: str = "v1"
    ) -> Optional[OutcomeRecord]:
        if not decision.goal or decision.status in ["BLOCKED", "NO_ACTION"]:
            return None

        goal_name = decision.goal.get("id", "")
        deadline_str = decision.goal.get("deadline", "")
        if not deadline_str:
            return None

        deadline = datetime.fromisoformat(deadline_str.replace('Z', '+00:00'))
        decision_time = datetime.fromisoformat(decision.trigger["received_at"].replace('Z', '+00:00'))

        # Check for unmeasurable goals
        if "social_share" in goal_name or "rating" in goal_name:
            return OutcomeRecord(
                outcome_id=f"OUT-{uuid.uuid4().hex[:8].upper()}",
                decision_id=decision.decision_id,
                viewer_id=decision.viewer_id,
                goal_id=goal_name,
                goal_name=goal_name,
                rule_version=rule_version,
                classification="INCONCLUSIVE",
                evaluated_at=eval_time,
                deadline=deadline,
                reason="Signal not observable in application event telemetry.",
                evidence_ids=decision.evidence
            )

        # Look for qualifying event in the observation window [decision_time, deadline]
        qualifying_event = None

        for ev in events:
            if ev.viewer_id != decision.viewer_id:
                continue
            # Event occurred during window
            if decision_time <= ev.timestamp <= deadline:
                if "first_full_episode" in goal_name:
                    if ev.event_type == "play":
                        pct = float(ev.payload.get("progress_pct", 0.0))
                        # Rule v1: 100%, Rule v2: >= 85%
                        threshold = 85.0 if rule_version == "v2" else 100.0
                        if pct >= threshold or ev.payload.get("completed"):
                            qualifying_event = ev
                            break

                elif "first_stream" in goal_name or "browse_to_watch" in goal_name:
                    if ev.event_type == "play":
                        qualifying_event = ev
                        break

                elif "first_paid_plan" in goal_name:
                    if ev.event_type == "purchase" and ev.payload.get("status") == "success":
                        qualifying_event = ev
                        break

                elif "return_day_2" in goal_name or "reengage" in goal_name:
                    if ev.event_type == "app_open":
                        qualifying_event = ev
                        break

        outcome_id = f"OUT-{uuid.uuid4().hex[:8].upper()}"

        if qualifying_event:
            record = OutcomeRecord(
                outcome_id=outcome_id,
                decision_id=decision.decision_id,
                viewer_id=decision.viewer_id,
                goal_id=goal_name,
                goal_name=goal_name,
                rule_version=rule_version,
                classification="SUCCEEDED",
                evaluated_at=eval_time,
                deadline=deadline,
                qualifying_event_id=qualifying_event.event_id,
                qualifying_event_time=qualifying_event.timestamp,
                reason=f"Qualifying event {qualifying_event.event_type} ({qualifying_event.event_id}) verified.",
                evidence_ids=[f"event:{qualifying_event.event_id}", f"goal_rule:{goal_name}-{rule_version}"]
            )
            self.state_store.record_outcome(record)
            return record

        elif eval_time >= deadline:
            record = OutcomeRecord(
                outcome_id=outcome_id,
                decision_id=decision.decision_id,
                viewer_id=decision.viewer_id,
                goal_id=goal_name,
                goal_name=goal_name,
                rule_version=rule_version,
                classification="FAILED",
                evaluated_at=eval_time,
                deadline=deadline,
                reason="Deadline passed without qualifying telemetry event.",
                evidence_ids=[f"goal_rule:{goal_name}-{rule_version}"]
            )
            self.state_store.record_outcome(record)
            return record

        else:
            # Observation window still open
            record = OutcomeRecord(
                outcome_id=outcome_id,
                decision_id=decision.decision_id,
                viewer_id=decision.viewer_id,
                goal_id=goal_name,
                goal_name=goal_name,
                rule_version=rule_version,
                classification="INCONCLUSIVE",
                evaluated_at=eval_time,
                deadline=deadline,
                reason="Goal observation window remains active; awaiting events.",
                evidence_ids=[f"goal_rule:{goal_name}-{rule_version}"]
            )
            self.state_store.record_outcome(record)
            return record

    def reevaluate_for_rule_update(
        self,
        target_goal_id: str,
        new_version: str,
        all_events: List[Event],
        eval_time: datetime
    ) -> List[OutcomeRecord]:
        """
        Targeted re-evaluation: ONLY re-evaluates decisions and active goals associated
        with target_goal_id, preserving provenance and avoiding blanket reprocessing.
        """
        updated_outcomes = []
        decisions = self.state_store.get_all_decisions()
        for d in decisions:
            if d.goal and target_goal_id in d.goal.get("id", ""):
                rec = self.evaluate_decision_outcome(
                    decision=d,
                    events=all_events,
                    eval_time=eval_time,
                    rule_version=new_version
                )
                if rec:
                    updated_outcomes.append(rec)
        return updated_outcomes
