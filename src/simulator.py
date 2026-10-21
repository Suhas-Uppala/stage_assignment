"""
Automation Simulator Engine for OTT Dialect Platform.
Uses ReplayOrchestrator to run real-time events and surprise scenarios,
capturing rich step-by-step telemetry for the visual automation interface.
"""
import copy
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.config import CONFIG
from src.ingestion.normalizer import EventNormalizer
from src.state.fact_resolver import FactResolver
from src.state.viewer_agent import ViewerAgent
from src.replay.orchestrator import ReplayOrchestrator
from src.replay.surprise_injector import SurpriseScenarioSuite


class AutomationSimulator:
    def __init__(self, db_path: str = "sample_run/simulator.db"):
        self.db_path = db_path
        self.orchestrator = ReplayOrchestrator(db_path=db_path)
        self.stream_events: List[Dict[str, Any]] = []
        self._load_stream("data/synthetic_pack/event_stream.jsonl")

    def _load_stream(self, path: str):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.stream_events.append(json.loads(line))

    def get_sample_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        samples = []
        for i, ev in enumerate(self.stream_events[:limit]):
            samples.append({
                "index": i,
                "event_id": ev.get("event_id"),
                "viewer_id": ev.get("viewer_id"),
                "event_type": ev.get("event_type"),
                "timestamp": ev.get("timestamp"),
                "dialect": ev.get("payload", {}).get("app_setting_dialect", "none")
            })
        return samples

    def run_step(self, raw_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an event through ReplayOrchestrator and return step-by-step trace for visualization.
        """
        start_time = time.perf_counter()
        logs: List[Dict[str, str]] = []

        def log(stage: str, msg: str, level: str = "INFO"):
            ts = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
            logs.append({"timestamp": ts, "stage": stage, "level": level, "message": msg})

        viewer_id = raw_event.get("viewer_id", "UNKNOWN")
        event_type = raw_event.get("event_type", "UNKNOWN")
        log("INGEST", f"Telemetry event '{event_type}' received for viewer {viewer_id}")

        # Normalize event
        event, err = EventNormalizer.normalize(raw_event)
        if err or not event:
            log("INGEST", f"Normalization error: {err}", "ERROR")
            steps = [{
                "step": 1, "name": "Ingestion & Validation", "status": "blocked",
                "badge": "INVALID", "summary": f"Normalization error: {err}",
                "details": {"error": err}
            }]
            return {"steps": steps, "logs": logs, "decision": None, "status": "BLOCKED"}

        # Run through orchestrator
        decision = self.orchestrator.process_trigger(raw_event)
        elapsed_total_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        # Inspect viewer state
        agent = ViewerAgent(viewer_id, self.orchestrator.state_store)
        profile_list = self.orchestrator.profiles_by_viewer.get(viewer_id, [])
        resolved_profile = FactResolver.resolve_profile(profile_list)
        dialect_res = FactResolver.resolve_dialect(event, resolved_profile, agent.state, event.received_at)
        sub_status, sub_src, _ = FactResolver.resolve_subscription(event, resolved_profile, agent.state, event.received_at)

        # Build 7-stage visualization steps
        steps: List[Dict[str, Any]] = []

        # Stage 1: Ingest & Deduplication
        is_stale = event.event_age_s > CONFIG.MAX_EVENT_AGE_SECONDS
        s1_status = "warning" if is_stale else "passed"
        s1_badge = "STALE BUFFERED" if is_stale else "VALID"
        s1_sum = f"Normalized event {event.event_id}. Age: {round(event.event_age_s, 1)}s. Deduplicated: OK."
        if is_stale:
            s1_sum = f"Stale offline buffer detected (age {round(event.event_age_s, 1)}s > threshold {CONFIG.MAX_EVENT_AGE_SECONDS}s)."
            log("INGEST", s1_sum, "WARN")
        else:
            log("INGEST", s1_sum)

        steps.append({
            "step": 1,
            "name": "Ingestion & Normalization",
            "status": s1_status,
            "badge": s1_badge,
            "summary": s1_sum,
            "details": {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "event_age_s": event.event_age_s,
                "received_at": event.received_at.isoformat()
            }
        })

        # Stage 2: Fact Resolution
        if decision and decision.reason == "stale_buffered_trigger":
            steps.append({
                "step": 2, "name": "Fact Resolution", "status": "skipped",
                "badge": "SKIPPED", "summary": "Skipped due to stale trigger event.", "details": {}
            })
        else:
            conflicts = dialect_res.conflicts or []
            s2_badge = f"DIALECT: {dialect_res.used.upper()}"
            s2_sum = f"Dialect resolved: {dialect_res.used} ({dialect_res.source}) | Sub: {sub_status} ({sub_src})"
            if conflicts:
                s2_sum += f" | Conflicts: {len(conflicts)} detected"
            log("FACTS", s2_sum)
            steps.append({
                "step": 2,
                "name": "Fact Resolution & Provenance",
                "status": "passed",
                "badge": s2_badge,
                "summary": s2_sum,
                "details": {
                    "dialect": dialect_res.used,
                    "source": dialect_res.source,
                    "conflicts": conflicts,
                    "subscription_status": sub_status
                }
            })

        # Stage 3: Goal Selection
        goal_name = "none"
        if decision and decision.goal:
            if isinstance(decision.goal, dict):
                goal_name = decision.goal.get("id", "none")
            elif hasattr(decision.goal, "id"):
                goal_name = decision.goal.id
        elif agent.state.active_goal:
            goal_name = agent.state.active_goal.name

        if decision and decision.reason == "stale_buffered_trigger":
            steps.append({
                "step": 3, "name": "Goal Selection", "status": "skipped",
                "badge": "SKIPPED", "summary": "Skipped due to stale trigger.", "details": {}
            })
        else:
            s3_status = "passed" if goal_name != "none" else "info"
            s3_sum = f"Single active goal: {goal_name}"
            log("GOALS", s3_sum)
            steps.append({
                "step": 3,
                "name": "Single Active Goal Selection",
                "status": s3_status,
                "badge": goal_name,
                "summary": s3_sum,
                "details": {
                    "goal_id": goal_name,
                    "deadline": agent.state.active_goal.deadline.isoformat() if agent.state.active_goal else None
                }
            })

        # Stage 4: Intervention Planning (LLM)
        if decision and decision.reason == "stale_buffered_trigger":
            steps.append({
                "step": 4, "name": "Intervention Planning", "status": "skipped",
                "badge": "SKIPPED", "summary": "Skipped due to stale trigger.", "details": {}
            })
        else:
            action_planned = decision.action if decision else "HOME_PAGE"
            content_count = len(decision.content) if decision else 0
            s4_sum = f"Planned action: {action_planned} | Content matches: {content_count} titles"
            log("PLANNER", s4_sum)
            steps.append({
                "step": 4,
                "name": "Intervention Planning (LLM Bounded)",
                "status": "passed",
                "badge": action_planned,
                "summary": s4_sum,
                "details": {
                    "action": action_planned,
                    "content_refs": decision.content if decision else []
                }
            })

        # Stage 5: Independent Verification Gate
        if decision and decision.reason == "stale_buffered_trigger":
            steps.append({
                "step": 5, "name": "Verification Gate", "status": "skipped",
                "badge": "SKIPPED", "summary": "Skipped due to stale trigger.", "details": {}
            })
        elif decision:
            checks_dict = decision.checks if isinstance(decision.checks, dict) else (decision.checks.model_dump() if hasattr(decision.checks, "model_dump") else {})
            passed_checks = checks_dict.get("passed", [])
            failed_checks = checks_dict.get("failed", [])
            s5_verified = len(failed_checks) == 0
            s5_status = "passed" if s5_verified else "blocked"
            s5_badge = "VERIFIED" if s5_verified else "BLOCKED"
            s5_sum = f"Passed: {len(passed_checks)} | Failed: {len(failed_checks)}"
            log("VERIFIER", f"Safety Gate: {s5_badge} (Passed: {passed_checks}, Failed: {failed_checks})")
            steps.append({
                "step": 5,
                "name": "Independent Verification Gate",
                "status": s5_status,
                "badge": s5_badge,
                "summary": s5_sum,
                "details": {
                    "passed": passed_checks,
                    "failed": failed_checks,
                    "is_verified": s5_verified
                }
            })
        else:
            steps.append({
                "step": 5, "name": "Verification Gate", "status": "info",
                "badge": "N/A", "summary": "No intervention required to verify.", "details": {}
            })

        # Stage 6: Action Execution
        dec_status = decision.status if decision else "STATE_UPDATED"
        dec_action = decision.action if decision else "NO_ACTION"
        dec_lat = decision.decided_in_ms if decision else elapsed_total_ms
        s6_status = "passed" if dec_status == "PUBLISHED" else ("warning" if dec_status in ("NO_ACTION", "STATE_UPDATED") else "blocked")
        s6_sum = f"Action: {dec_action} | Status: {dec_status} | Latency: {dec_lat} ms"
        log("EXECUTE", s6_sum)
        steps.append({
            "step": 6,
            "name": "Idempotent Execution Dispatch",
            "status": s6_status,
            "badge": dec_status,
            "summary": s6_sum,
            "details": {
                "action": dec_action,
                "status": dec_status,
                "latency_ms": dec_lat,
                "reason": decision.reason if decision else None
            }
        })

        # Stage 7: State Persistence & Outcome
        s7_sum = f"State v{agent.state.version} committed to SQLite WAL. Telemetry watcher active."
        log("STORAGE", s7_sum)
        steps.append({
            "step": 7,
            "name": "State Persistence & Telemetry Watcher",
            "status": "passed",
            "badge": f"STATE v{agent.state.version}",
            "summary": s7_sum,
            "details": {
                "version": agent.state.version,
                "viewer_id": viewer_id
            }
        })

        dec_dict = decision.model_dump() if decision else {
            "viewer_id": viewer_id, "action": "NO_ACTION", "status": "STATE_UPDATED",
            "decided_in_ms": elapsed_total_ms, "checks": {"passed": [], "failed": []}
        }

        return {
            "steps": steps,
            "logs": logs,
            "decision": dec_dict,
            "status": dec_status,
            "viewer_state": {
                "viewer_id": agent.state.viewer_id,
                "version": agent.state.version,
                "dialect": dialect_res.used,
                "subscription_status": sub_status,
                "active_goal": goal_name,
                "completed_episodes": agent.state.completed_episodes,
                "watched_titles": agent.state.watched_titles
            }
        }

    def run_surprise_scenario(self, scenario_id: int) -> Dict[str, Any]:
        """Run official assignment surprise scenario and return execution trace."""
        if scenario_id == 1:
            ev = SurpriseScenarioSuite.get_buffered_offline_event()
        elif scenario_id == 2:
            ev = SurpriseScenarioSuite.get_purchase_after_stale_profile_event()
        elif scenario_id == 3:
            ev = SurpriseScenarioSuite.get_three_way_dialect_conflict_event()
        elif scenario_id == 6:
            ev = SurpriseScenarioSuite.get_prompt_injection_event()
        else:
            now = datetime.now(timezone.utc)
            ev = {
                "event_id": f"SIM_NORMAL_{uuid.uuid4().hex[:6]}",
                "viewer_id": "V-2291",
                "event_type": "app_open",
                "timestamp": now.isoformat(),
                "received_at": now.isoformat(),
                "payload": {"app_setting_dialect": "d3", "app_setting_language": "Bhojpuri"}
            }

        res = self.run_step(ev)
        res["scenario_id"] = scenario_id
        res["raw_event"] = ev
        return res
