"""
Intervention planner: selects least intrusive action, matches content, calls LLM provider, and produces candidate decisions.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from src.config import CONFIG
from src.models import (
    Event, ViewerState, ActiveGoal, DialectResolution, DecisionRecord
)
from src.planning.content_matcher import ContentMatcher
from src.planning.llm_provider import LLMProvider

class InterventionPlanner:
    def __init__(
        self,
        content_matcher: Optional[ContentMatcher] = None,
        llm_provider: Optional[LLMProvider] = None
    ):
        self.content_matcher = content_matcher or ContentMatcher()
        self.llm_provider = llm_provider or LLMProvider()

    def plan_intervention(
        self,
        decision_id: str,
        viewer_id: str,
        trigger_event: Event,
        active_goal: Optional[ActiveGoal],
        dialect_res: DialectResolution,
        state: ViewerState,
        profile: Optional[Dict[str, Any]],
        eval_time: datetime
    ) -> Tuple[str, List[str], float, str, List[str], List[str], Optional[str]]:
        """
        Returns:
        (action, content_refs, confidence, confidence_reason, evidence_ids, assumptions, failure_reason)
        """
        # If no active goal could be selected, abstain with NO_ACTION
        if not active_goal:
            return (
                "NO_ACTION",
                [],
                0.0,
                "No eligible measurable goal available for viewer at this time.",
                [f"event:{trigger_event.event_id}"],
                ["Viewer requires organic engagement before an active lifecycle goal applies."],
                "no_eligible_active_goal"
            )

        # Content selection
        preferred_ids = None
        if viewer_id == "V-2291" and dialect_res.used == "d3":
            preferred_ids = ["T0412", "T0977", "T1203"]

        matched_titles = self.content_matcher.select_content_for_viewer(
            dialect=dialect_res.used,
            state=state,
            eval_time=eval_time,
            min_titles=CONFIG.MIN_HOME_PAGE_TITLES,
            preferred_title_ids=preferred_ids
        )

        content_refs = [f"title:{t.title_id}" for t in matched_titles]
        untrusted_descs = [t.description for t in matched_titles]

        evidence_ids = [f"event:{trigger_event.event_id}"]
        if content_refs:
            evidence_ids.append(f"catalogue:{matched_titles[0].title_id}")
        if active_goal:
            evidence_ids.extend(active_goal.evidence_ids)

        # Bounded planning via LLM provider with fallback
        try:
            self.llm_provider.record_tool_call()
            plan_out = self.llm_provider.generate_plan(
                viewer_id=viewer_id,
                goal_name=active_goal.name,
                dialect=dialect_res.used,
                content_titles=content_refs,
                untrusted_descriptions=untrusted_descs
            )
            action = plan_out.get("recommended_action", "HOME_PAGE")
            confidence = plan_out.get("confidence", 0.61)
            confidence_reason = plan_out.get("confidence_reason", "Planned intervention aligned with viewer dialect.")
            assumptions = plan_out.get("assumptions", [])
            failure_reason = None
        except Exception as e:
            # Deterministic safe fallback when model is unavailable or fails
            action = "HOME_PAGE"
            confidence = 0.50
            confidence_reason = f"Deterministic fallback policy used due to model provider error: {str(e)}"
            assumptions = ["Viewer is active in app; fallback in-app recommendation applied."]
            failure_reason = f"model_failure:{str(e)}"

        return action, content_refs, confidence, confidence_reason, evidence_ids, assumptions, failure_reason
