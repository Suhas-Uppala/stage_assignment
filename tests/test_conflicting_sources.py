"""
Mandatory Test 2: Conflicting sources, fact-specific precedence, and provenance.
"""
from datetime import datetime, timedelta, timezone
from src.state.fact_resolver import FactResolver
from src.models import ViewerState, Event

def test_three_way_dialect_conflict(test_orchestrator):
    """
    Verifies that when app_setting (d3), profile (d1), and campaign link (d2) conflict:
    1. app_setting is prioritized as the authority for in-app experience.
    2. All conflicting sources are explicitly recorded in dialect.conflicts with provenance.
    """
    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    raw_event = {
        "event_id": "EV_CONFLICT_01",
        "viewer_id": "V-CONFLICT-01",
        "event_type": "app_open",
        "timestamp": now.isoformat(),
        "received_at": (now + timedelta(seconds=2)).isoformat(),
        "payload": {
            "app_setting_dialect": "d3",
            "campaign_link": "https://ott.example.com/watch?dialect=d2"
        }
    }
    # Mock profile with dialect d1
    test_orchestrator.profiles_by_viewer["V-CONFLICT-01"] = [{
        "viewer_id": "V-CONFLICT-01",
        "preferred_dialect": "d1",
        "subscription_status": "free",
        "updated_at": (now - timedelta(days=1)).isoformat()
    }]

    decision = test_orchestrator.process_trigger(raw_event)
    assert decision is not None
    assert decision.dialect["used"] == "d3"
    assert decision.dialect["source"] == "app_setting"
    assert "profile:d1" in decision.dialect["conflicts"]
    assert "campaign:d2" in decision.dialect["conflicts"]

def test_purchase_event_overrides_stale_profile(test_orchestrator):
    """
    Verifies that a real-time purchase event immediately promotes subscription status
    to 'paid', overriding a 1-day stale profile snapshot that claimed 'free'.
    """
    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    v_id = "V-PURCHASE-01"

    # Profile snapshot says free
    test_orchestrator.profiles_by_viewer[v_id] = [{
        "viewer_id": v_id,
        "subscription_status": "free",
        "preferred_dialect": "d1",
        "updated_at": (now - timedelta(days=1)).isoformat()
    }]

    # Ingest initial app_open (status is free)
    ev1 = {
        "event_id": "EV_APP_OPEN_01",
        "viewer_id": v_id,
        "event_type": "app_open",
        "timestamp": now.isoformat(),
        "received_at": (now + timedelta(seconds=1)).isoformat(),
        "payload": {"app_setting_dialect": "d1"}
    }
    d1 = test_orchestrator.process_trigger(ev1)
    
    # State before purchase
    state_before = test_orchestrator.state_store.get_viewer_state(v_id)
    assert state_before.facts["subscription_status"].value == "free"

    # Purchase event arrives 2 minutes later
    ev2 = {
        "event_id": "EV_PURCHASE_02",
        "viewer_id": v_id,
        "event_type": "purchase",
        "timestamp": (now + timedelta(minutes=2)).isoformat(),
        "received_at": (now + timedelta(minutes=2, seconds=3)).isoformat(),
        "payload": {
            "plan_id": "annual_vip",
            "amount": 999,
            "status": "success",
            "subscription_status": "paid"
        }
    }
    test_orchestrator.process_trigger(ev2)

    # State after purchase: status is paid, source is event_stream
    state_after = test_orchestrator.state_store.get_viewer_state(v_id)
    assert state_after.facts["subscription_status"].value == "paid"
    assert state_after.facts["subscription_status"].source == "event_stream"

def test_profile_snapshot_deduplication():
    """
    Verifies that when a daily warehouse export contains two versions of a profile,
    the resolver selects the newer record by updated_at and avoids inconsistent state.
    """
    profiles = [
        {
            "viewer_id": "V-DUP-PROF",
            "preferred_dialect": "d1",
            "subscription_status": "free",
            "updated_at": "2026-09-01T00:00:00Z" # older
        },
        {
            "viewer_id": "V-DUP-PROF",
            "preferred_dialect": "d3",
            "subscription_status": "paid",
            "updated_at": "2026-09-05T00:00:00Z" # newer
        }
    ]
    resolved = FactResolver.resolve_profile(profiles)
    assert resolved is not None
    assert resolved["preferred_dialect"] == "d3"
    assert resolved["subscription_status"] == "paid"
