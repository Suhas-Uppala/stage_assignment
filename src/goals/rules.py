"""
Goal rules engine: eligibility logic, evidence verification, rule versioning, and missing signal handling.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from src.models import Event, ViewerState, GoalDefinition

class GoalRuleEngine:
    def __init__(self, catalogue_path: str = "data/catalogue/goal_catalogue.json"):
        self.catalogue_path = catalogue_path
        self.goals_by_id_version: Dict[Tuple[str, str], GoalDefinition] = {}
        self.load_catalogue()

    def load_catalogue(self):
        if not os.path.exists(self.catalogue_path):
            return
        with open(self.catalogue_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                goal_def = GoalDefinition.model_validate(item)
                self.goals_by_id_version[(goal_def.goal_id, goal_def.version)] = goal_def

    def get_goal_definition(self, goal_id: str, version: str = "v1") -> Optional[GoalDefinition]:
        return self.goals_by_id_version.get((goal_id, version))

    def evaluate_eligibility(
        self,
        goal_id: str,
        version: str,
        state: ViewerState,
        trigger_event: Event,
        profile: Optional[Dict[str, Any]]
    ) -> Tuple[bool, List[str], Optional[str]]:
        """
        Returns (is_eligible, evidence_ids, rejection_reason)
        """
        goal_def = self.get_goal_definition(goal_id, version)
        if not goal_def:
            return False, [], f"unknown_goal:{goal_id}_{version}"

        # 1. Check if goal is measurable
        if not goal_def.is_measurable:
            return False, [], f"unmeasurable_goal:{goal_def.missing_signal}"

        evidence: List[str] = [f"goal_rule:{goal_id}-{version}"]
        
        # Pull facts
        sub_fact = state.facts.get("subscription_status")
        sub_status = sub_fact.value if sub_fact else "free"
        if sub_fact and sub_fact.source == "event_stream":
            evidence.append("evidence:realtime_purchase_verified")
        elif profile:
            evidence.append(f"profile:{profile.get('viewer_id')}")

        if trigger_event:
            evidence.append(f"event:{trigger_event.event_id}")

        # --- Rule Evaluations ---
        if goal_id == "G01": # first_stream_24h
            if len(state.watched_titles) > 0 or state.completed_episodes > 0:
                return False, [], "goal_already_achieved:viewer_already_streamed"
            return True, evidence, None

        elif goal_id == "G02": # first_full_episode_3d
            if state.completed_episodes > 0:
                return False, [], "goal_already_achieved:first_episode_already_completed"
            return True, evidence, None

        elif goal_id == "G03": # browse_to_watch_1h
            if trigger_event.event_type not in ["app_open", "search", "page_view"]:
                return False, [], "trigger_not_browsing"
            return True, evidence, None

        elif goal_id == "G04": # return_day_2_visit
            return True, evidence, None

        elif goal_id == "G05": # first_paid_plan_7d
            if sub_status == "paid":
                return False, [], "goal_already_achieved:already_subscribed_to_paid_plan"
            return True, evidence, None

        elif goal_id == "G06": # renew_subscription_48h
            if sub_status not in ["expiring", "due_renewal"]:
                return False, [], "not_eligible:subscription_not_expiring"
            return True, evidence, None

        elif goal_id == "G07": # reengage_churned_14d
            return True, evidence, None

        elif goal_id == "G08": # weekend_binge_watch
            # Check weekend (Friday=4, Saturday=5, Sunday=6)
            weekday = trigger_event.timestamp.weekday()
            if weekday not in [4, 5, 6]:
                return False, [], "not_eligible:not_weekend"
            return True, evidence, None

        elif goal_id == "G09": # dialect_exploration_5d
            if len(state.watched_titles) < 2:
                return False, [], "not_eligible:insufficient_primary_dialect_history"
            return True, evidence, None

        elif goal_id == "G12": # micro_drama_completion_48h
            return True, evidence, None

        return False, [], f"unimplemented_goal_rule:{goal_id}"
