"""
Test suite for outcome evaluation, missing signals, and causal holdout impact measurement.
"""
from datetime import datetime, timedelta, timezone
from src.models import DecisionRecord, Event
from src.outcome.impact_analyzer import ImpactAnalyzer

def test_missing_unobservable_signals_inconclusive(test_orchestrator):
    """
    Verifies that goals relying on uninstrumented telemetry signals (e.g. social share G10,
    CSAT rating G11) are classified as INCONCLUSIVE and never falsely marked as succeeded or failed.
    """
    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    decision = DecisionRecord(
        decision_id="D-UNOBS-01",
        viewer_id="V-UNOBS-01",
        trigger={"event": "app_open", "received_at": now.isoformat(), "event_age_s": 2.0},
        goal={"id": "social_share_episode", "deadline": (now + timedelta(days=3)).isoformat()},
        action="IN_APP_MESSAGE",
        dialect={"used": "d1", "source": "profile", "conflicts": []},
        content=["title:T0001"],
        confidence=0.5,
        evidence=["event:E1"],
        assumptions=[],
        checks={"passed": ["eligibility"], "failed": []},
        decided_in_ms=45.0,
        status="PUBLISHED",
        idempotency_key="IDEM_UNOBS_01"
    )

    eval_time = now + timedelta(days=4)
    outcome = test_orchestrator.evaluator.evaluate_decision_outcome(
        decision=decision,
        events=[],
        eval_time=eval_time
    )

    assert outcome is not None
    assert outcome.classification == "INCONCLUSIVE"
    assert "not observable" in outcome.reason.lower()

def test_causal_holdout_uplift_math():
    """
    Verifies statistical formulas for Intention-To-Treat (ITT), Absolute Uplift (pp),
    Relative Uplift (%), Standard Error, 95% Confidence Intervals, and p-values.
    """
    # Treatment: 4000 total, 752 converted (18.8%)
    # Holdout: 1000 total, 142 converted (14.2%)
    stats = ImpactAnalyzer.calculate_uplift_stats(
        n_treat=4000,
        c_treat=752,
        n_hold=1000,
        c_hold=142
    )

    assert stats["p_treat_pct"] == 18.8
    assert stats["p_hold_pct"] == 14.2
    assert stats["abs_uplift_pp"] == 4.6 # 18.8 - 14.2
    assert stats["rel_uplift_pct"] == 32.39 # 4.6 / 14.2 * 100
    assert stats["ci_95_pp"][0] > 2.0 # Lower bound ~ 2.15 pp
    assert stats["ci_95_pp"][1] < 7.1 # Upper bound ~ 7.05 pp
    assert stats["z_score"] > 3.0 # Highly significant
    assert stats["p_value"] < 0.001
    assert stats["statistically_significant"] is True

def test_impact_report_generation(test_orchestrator, temp_dir):
    """
    Verifies generation of the markdown impact report highlighting selection bias.
    """
    import os
    analyzer = ImpactAnalyzer()
    out_file = os.path.join(temp_dir, "test_impact_report.md")
    report = analyzer.generate_impact_report(output_markdown_path=out_file)

    assert os.path.exists(out_file)
    assert "Causal Uplift vs. Naive Observational Comparison" in report
    assert "Selection Bias" in report
    assert "Intention-To-Treat" in report
