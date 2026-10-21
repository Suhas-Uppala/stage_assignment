"""
Mandatory Test 3: Tool and dependency failure handling, budgets, and safe fallbacks.
"""
import pytest
from datetime import datetime, timedelta, timezone
from src.planning.llm_provider import (
    LLMProvider, ModelCallBudgetExceeded, ToolCallBudgetExceeded
)

def test_model_service_failure_graceful_fallback(test_orchestrator):
    """
    Verifies that when the LLM service raises an exception (e.g. 503 unavailable),
    the system does not crash and safely falls back to the deterministic policy.
    """
    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    raw_event = {
        "event_id": "EV_FAIL_01",
        "viewer_id": "V-FAIL-01",
        "event_type": "app_open",
        "timestamp": now.isoformat(),
        "received_at": (now + timedelta(seconds=1)).isoformat(),
        "payload": {"app_setting_dialect": "d3"}
    }

    # Simulate LLM failure
    test_orchestrator.llm_provider.simulate_failure = True

    decision = test_orchestrator.process_trigger(raw_event)
    assert decision is not None
    # Action published via deterministic fallback
    assert decision.action == "HOME_PAGE"
    assert "fallback" in decision.confidence_reason.lower()
    assert decision.decided_in_ms < 5000.0 # Well within 60s budget

def test_model_call_budget_enforcement():
    """
    Verifies that model calls exceeding the configurable budget (8 max) are blocked.
    """
    provider = LLMProvider(max_model_calls=3)
    
    # 3 calls succeed
    for _ in range(3):
        provider.generate_plan(
            viewer_id="V-1",
            goal_name="test_goal",
            dialect="d1",
            content_titles=["title:T1"]
        )

    # 4th call raises ModelCallBudgetExceeded
    with pytest.raises(ModelCallBudgetExceeded):
        provider.generate_plan(
            viewer_id="V-1",
            goal_name="test_goal",
            dialect="d1",
            content_titles=["title:T1"]
        )

def test_tool_call_budget_enforcement():
    """
    Verifies that tool calls exceeding the configurable budget (20 max) are blocked.
    """
    provider = LLMProvider(max_tool_calls=5)
    for _ in range(5):
        provider.record_tool_call()

    with pytest.raises(ToolCallBudgetExceeded):
        provider.record_tool_call()

def test_model_slowdown_timeout_handling(test_orchestrator):
    """
    Verifies that a slow model call triggers a timeout and falls back safely
    within the overall latency budget.
    """
    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    raw_event = {
        "event_id": "EV_SLOW_01",
        "viewer_id": "V-SLOW-01",
        "event_type": "app_open",
        "timestamp": now.isoformat(),
        "received_at": (now + timedelta(seconds=1)).isoformat(),
        "payload": {"app_setting_dialect": "d3"}
    }

    test_orchestrator.llm_provider.simulate_slow_down = True
    decision = test_orchestrator.process_trigger(raw_event)
    assert decision is not None
    assert decision.action == "HOME_PAGE"
    assert "timeout" in decision.confidence_reason.lower() or "fallback" in decision.confidence_reason.lower()
