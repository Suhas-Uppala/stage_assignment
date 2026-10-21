"""
Test suite for Decision JSON schema validation, state persistence across restart, and single active goal ownership.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from src.models import DecisionRecord, ViewerState, ViewerFact, ActiveGoal
from src.storage.database import Database
from src.storage.state_store import StateStore

def test_state_persistence_across_process_restart(temp_dir):
    """
    Verifies that per-viewer state is durably persisted in SQLite and survives
    process restart / new connection instances without state loss.
    """
    db_path = os.path.join(temp_dir, "restart_test.db")
    
    # Instance 1: write state
    store1 = StateStore(Database(db_path))
    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    
    state1 = ViewerState(
        viewer_id="V-RESTART-01",
        completed_episodes=3,
        watched_titles=["T0001", "T0002"]
    )
    state1.facts["preferred_dialect"] = ViewerFact(
        fact_key="preferred_dialect",
        value="d3",
        source="app_setting",
        recorded_at=now,
        conflicts=[{"source": "profile", "value": "d1"}]
    )
    state1.active_goal = ActiveGoal(
        goal_id="first_full_episode_3d",
        name="first_full_episode_3d",
        version="v1",
        selected_at=now,
        deadline=now + timedelta(days=3),
        success_signal="play",
        target_metric="play"
    )
    store1.save_viewer_state(state1)

    # Process restart: Instance 2 opens same db file
    store2 = StateStore(Database(db_path))
    recovered = store2.get_viewer_state("V-RESTART-01")

    assert recovered.viewer_id == "V-RESTART-01"
    assert recovered.completed_episodes == 3
    assert recovered.watched_titles == ["T0001", "T0002"]
    assert recovered.facts["preferred_dialect"].value == "d3"
    assert recovered.facts["preferred_dialect"].conflicts[0]["value"] == "d1"
    assert recovered.active_goal is not None
    assert recovered.active_goal.name == "first_full_episode_3d"

def test_single_active_goal_ownership(test_orchestrator):
    """
    Verifies that one logical agent owns the viewer's lifecycle and never creates
    competing active goals for the same viewer.
    """
    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    v_id = "V-ONE-GOAL-01"

    # First event sets active goal
    ev1 = {
        "event_id": "EV_OG_1",
        "viewer_id": v_id,
        "event_type": "app_open",
        "timestamp": now.isoformat(),
        "received_at": (now + timedelta(seconds=2)).isoformat(),
        "payload": {"app_setting_dialect": "d3"}
    }
    d1 = test_orchestrator.process_trigger(ev1)
    assert d1.goal is not None
    first_goal_id = d1.goal["id"]

    # Second event 1 hour later (goal still in flight)
    ev2 = {
        "event_id": "EV_OG_2",
        "viewer_id": v_id,
        "event_type": "app_open",
        "timestamp": (now + timedelta(hours=1)).isoformat(),
        "received_at": (now + timedelta(hours=1, seconds=3)).isoformat(),
        "payload": {"app_setting_dialect": "d3"}
    }
    d2 = test_orchestrator.process_trigger(ev2)
    # The active goal remains identical and was not overwritten
    assert d2.goal["id"] == first_goal_id
    
    state = test_orchestrator.state_store.get_viewer_state(v_id)
    assert state.active_goal.name == first_goal_id

def test_sample_run_decisions_json_schema_valid():
    """
    Validates that all decisions generated in sample_run/decisions.jsonl
    strictly adhere to the Pydantic DecisionRecord schema.
    """
    path = "sample_run/decisions.jsonl"
    if not os.path.exists(path):
        return

    count = 0
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            # Validates with Pydantic
            record = DecisionRecord.model_validate(data)
            assert record.decision_id is not None
            assert record.viewer_id is not None
            assert record.trigger["event"] is not None
            assert record.trigger["event_age_s"] is not None
            assert "used" in record.dialect
            assert "passed" in record.checks
            assert "failed" in record.checks
            assert record.decided_in_ms >= 0.0
            assert record.status in ["PUBLISHED", "BLOCKED", "NO_ACTION", "FAILED"]
            count += 1
    assert count > 0
