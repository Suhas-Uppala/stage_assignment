"""
Mandatory Test 1: Late or duplicate trigger handling and idempotency.
"""
from datetime import datetime, timedelta, timezone
from src.config import CONFIG
from src.replay.orchestrator import ReplayOrchestrator

def test_late_buffered_offline_trigger(test_orchestrator):
    """
    Verifies that a buffered offline trigger (event_age_s > 300s)
    is not treated as a fresh app open and returns a safe NO_ACTION.
    """
    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    stale_time = now - timedelta(days=3) # 3 days old

    raw_event = {
        "event_id": "EV_STALE_TEST_01",
        "viewer_id": "V-TEST-001",
        "event_type": "app_open",
        "timestamp": stale_time.isoformat(),
        "received_at": now.isoformat(),
        "payload": {"app_setting_dialect": "d1"}
    }

    decision = test_orchestrator.process_trigger(raw_event)
    assert decision is not None
    assert decision.action == "NO_ACTION"
    assert decision.status == "NO_ACTION"
    assert decision.reason == "stale_buffered_trigger"
    assert decision.trigger["event_age_s"] > CONFIG.MAX_EVENT_AGE_SECONDS
    assert "staleness_detection" in decision.checks["passed"]

def test_duplicate_trigger_idempotency(test_orchestrator):
    """
    Verifies that duplicate triggers arriving multiple times are handled
    idempotently without creating duplicate external side-effects or competing plans.
    """
    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    raw_event = {
        "event_id": "EV_DUP_TEST_01",
        "viewer_id": "V-TEST-002",
        "event_type": "app_open",
        "timestamp": now.isoformat(),
        "received_at": (now + timedelta(seconds=2)).isoformat(),
        "payload": {"app_setting_dialect": "d2"}
    }

    # First arrival: processes normally
    d1 = test_orchestrator.process_trigger(raw_event)
    assert d1 is not None
    assert d1.status in ["PUBLISHED", "NO_ACTION"]

    # Second arrival: identical trigger event
    d2 = test_orchestrator.process_trigger(raw_event)
    assert d2 is not None
    # Idempotent: returns the cached decision or NO_ACTION duplicate
    assert d2.idempotency_key == d1.idempotency_key

    # Check database records: should not duplicate decisions for same key
    decisions = [d for d in test_orchestrator.state_store.get_all_decisions() if d.viewer_id == "V-TEST-002"]
    assert len(decisions) == 1

def test_duplicate_external_actions_prevention(test_orchestrator):
    """
    Verifies that the action executor prevents duplicate external actions for the same idempotency key.
    """
    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    agent = test_orchestrator.state_store.get_viewer_state("V-TEST-003")
    
    from src.models import ChecksResult
    checks = ChecksResult(passed=["eligibility"], failed=[])
    
    act1 = test_orchestrator.executor.execute(
        decision_id="D-ACT-1",
        viewer_id="V-TEST-003",
        action_type="HOME_PAGE",
        content_refs=["title:T0001", "title:T0002", "title:T0003"],
        is_verified=True,
        checks=checks,
        idempotency_key="IDEM_KEY_TEST_99",
        eval_time=now,
        viewer_agent=None
    )

    # Attempt to execute same action again with same idempotency key
    act2 = test_orchestrator.executor.execute(
        decision_id="D-ACT-2",
        viewer_id="V-TEST-003",
        action_type="HOME_PAGE",
        content_refs=["title:T0001", "title:T0002", "title:T0003"],
        is_verified=True,
        checks=checks,
        idempotency_key="IDEM_KEY_TEST_99",
        eval_time=now,
        viewer_agent=None
    )

    assert act1.action_id == act2.action_id
    all_acts = [a for a in test_orchestrator.state_store.get_all_actions() if a.viewer_id == "V-TEST-003"]
    assert len(all_acts) == 1
