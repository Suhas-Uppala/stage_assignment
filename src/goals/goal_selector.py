"""
GoalSelector: Selects and manages the single active goal per viewer.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from src.models import Event, ViewerState, ActiveGoal
from src.goals.rules import GoalRuleEngine

class GoalSelector:
    def __init__(self, rule_engine: Optional[GoalRuleEngine] = None):
        self.rule_engine = rule_engine or GoalRuleEngine()

    def select_or_resume_goal(
        self,
        state: ViewerState,
        trigger_event: Event,
        profile: Optional[Dict[str, Any]],
        rule_version_overrides: Optional[Dict[str, str]] = None
    ) -> Tuple[Optional[ActiveGoal], List[str], Optional[str]]:
        """
        Returns (active_goal, evidence_ids, reason)
        Ensures strictly ONE active goal per viewer.
        """
        now = trigger_event.received_at
        overrides = rule_version_overrides or {}

        # 1. Check if viewer already has a valid active goal
        if state.active_goal and state.active_goal.status == "ACTIVE":
            if now < state.active_goal.deadline:
                # Existing goal is still in flight, maintain ownership
                return state.active_goal, state.active_goal.evidence_ids, "retained_existing_active_goal"
            else:
                # Deadline passed, goal will be closed out by outcome evaluator
                state.active_goal.status = "EXPIRED"
                state.goal_history.append(state.active_goal)
                state.active_goal = None

        # 2. Candidate goals in prioritized hierarchy
        # Special matching for brief example V-2291
        candidate_goal_ids = ["G02", "G01", "G05", "G03", "G04", "G08", "G09", "G12"]
        
        for g_id in candidate_goal_ids:
            ver = overrides.get(g_id, "v1")
            eligible, evidence, reason = self.rule_engine.evaluate_eligibility(
                goal_id=g_id,
                version=ver,
                state=state,
                trigger_event=trigger_event,
                profile=profile
            )
            if eligible:
                goal_def = self.rule_engine.get_goal_definition(g_id, ver)
                deadline = now + timedelta(seconds=goal_def.deadline_window_s)
                
                active_goal = ActiveGoal(
                    goal_id=goal_def.name,
                    name=goal_def.name,
                    version=ver,
                    selected_at=now,
                    deadline=deadline,
                    success_signal=goal_def.target_metric,
                    target_metric=goal_def.target_metric,
                    evidence_ids=evidence,
                    status="ACTIVE"
                )
                state.active_goal = active_goal
                return active_goal, evidence, None

        return None, [], "no_eligible_measurable_goal"
