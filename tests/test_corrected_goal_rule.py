"""
Mandatory Test 4: Corrected goal rule versioning and targeted re-evaluation.
"""
from datetime import datetime, timedelta, timezone
from src.models import Event, DecisionRecord

def test_corrected_goal_rule_v1_vs_v2(test_orchestrator):
    """
    Demonstrates handling of a goal rule corrected mid-replay:
    - Rule v1 of first_full_episode_3d: requires 100% completion.
    - Rule v2 of first_full_episode_3d: requires >= 85% completion (excluding credits).
    - An episode with 88% watch progress fails under v1, but succeeds under v2.
    """
    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    v_id = "V-RULE-01"

    # 1. Trigger app_open with rule version v1
    app_open_ev = {
        "event_id": "EV_RULE_APP_01",
        "viewer_id": v_id,
        "event_type": "app_open",
        "timestamp": now.isoformat(),
        "received_at": (now + timedelta(seconds=1)).isoformat(),
        "payload": {"app_setting_dialect": "d3"}
    }
    decision = test_orchestrator.process_trigger(app_open_ev, rule_version_overrides={"G02": "v1"})
    assert decision is not None
    assert decision.goal["id"] == "first_full_episode_3d"
    assert decision.rule_version == "v1"

    # 2. Subsequent play event: 88% progress
    play_time = now + timedelta(hours=2)
    play_event = Event(
        event_id="EV_PLAY_88PCT",
        viewer_id=v_id,
        event_type="play",
        timestamp=play_time,
        received_at=play_time + timedelta(seconds=2),
        payload={
            "title_id": "T0412",
            "progress_pct": 88.0,
            "completed": False
        }
    )

    eval_time = now + timedelta(days=4) # Past 3-day deadline

    # Evaluate under v1: should be FAILED because 88% < 100%
    outcome_v1 = test_orchestrator.evaluator.evaluate_decision_outcome(
        decision=decision,
        events=[play_event],
        eval_time=eval_time,
        rule_version="v1"
    )
    assert outcome_v1.classification == "FAILED"
    assert outcome_v1.rule_version == "v1"

    # Evaluate under corrected v2: should be SUCCEEDED because 88% >= 85%
    outcome_v2 = test_orchestrator.evaluator.evaluate_decision_outcome(
        decision=decision,
        events=[play_event],
        eval_time=eval_time,
        rule_version="v2"
    )
    assert outcome_v2.classification == "SUCCEEDED"
    assert outcome_v2.rule_version == "v2"
    assert outcome_v2.qualifying_event_id == "EV_PLAY_88PCT"

def test_targeted_reevaluation_does_not_reprocess_unaffected_viewers(test_orchestrator):
    """
    Verifies that when a goal rule is updated, only decisions pursuing that specific goal
    are re-evaluated, avoiding wasteful blanket reprocessing of the entire database.
    """
    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)

    # Viewer 1: pursuing first_full_episode_3d
    d1 = DecisionRecord(
        decision_id="D-TGT-1",
        viewer_id="V-TGT-1",
        trigger={"event": "app_open", "received_at": now.isoformat(), "event_age_s": 1.0},
        goal={"id": "first_full_episode_3d", "deadline": (now + timedelta(days=3)).isoformat()},
        action="HOME_PAGE",
        dialect={"used": "d3", "source": "app_setting", "conflicts": []},
        content=["title:T0412", "title:T0977", "title:T1203"],
        confidence=0.6,
        evidence=["event:EV1"],
        assumptions=[],
        checks={"passed": ["eligibility"], "failed": []},
        decided_in_ms=50.0,
        status="PUBLISHED",
        rule_version="v1",
        idempotency_key="IDEM_TGT_1"
    )
    test_orchestrator.state_store.record_decision(d1)

    # Viewer 2: pursuing first_paid_plan_7d (unaffected goal)
    d2 = DecisionRecord(
        decision_id="D-TGT-2",
        viewer_id="V-TGT-2",
        trigger={"event": "app_open", "received_at": now.isoformat(), "event_age_s": 1.0},
        goal={"id": "first_paid_plan_7d", "deadline": (now + timedelta(days=7)).isoformat()},
        action="HOME_PAGE",
        dialect={"used": "d3", "source": "app_setting", "conflicts": []},
        content=["title:T0412", "title:T0977", "title:T1203"],
        confidence=0.6,
        evidence=["event:EV2"],
        assumptions=[],
        checks={"passed": ["eligibility"], "failed": []},
        decided_in_ms=50.0,
        status="PUBLISHED",
        rule_version="v1",
        idempotency_key="IDEM_TGT_2"
    )
    test_orchestrator.state_store.record_decision(d2)

    # Perform targeted re-evaluation for first_full_episode_3d only
    updated = test_orchestrator.evaluator.reevaluate_for_rule_update(
        target_goal_id="first_full_episode_3d",
        new_version="v2",
        all_events=[],
        eval_time=now + timedelta(days=4)
    )

    # Only 1 decision re-evaluated, viewer 2 was untouched
    assert len(updated) == 1
    assert updated[0].decision_id == "D-TGT-1"
    assert updated[0].goal_name == "first_full_episode_3d"
