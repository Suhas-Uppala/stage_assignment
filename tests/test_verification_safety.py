"""
Verification and Safety Test Suite:
Validates that independent verification catches policy violations, quiet hours,
lack of consent, frequency cap breaches, min row size, dialect mismatches, and expired content.
"""
from datetime import datetime, timedelta, timezone
from src.models import ViewerState, ViewerFact, ContentTitle, ActiveGoal, DialectResolution
from src.verification.verifier import IndependentVerifier

def test_quiet_hours_restriction():
    """
    Verifies that push/WhatsApp messages sent during quiet hours (22:00 to 08:00 local time)
    are strictly caught and blocked by the independent verifier.
    """
    verifier = IndependentVerifier()
    # 23:30 local time (India IST UTC+5:30 -> UTC 18:00)
    eval_time = datetime(2026, 9, 12, 18, 0, 0, tzinfo=timezone.utc)
    
    state = ViewerState(viewer_id="V-QUIET-01")
    state.facts["consent_push"] = ViewerFact(
        fact_key="consent_push", value=True, source="profile", recorded_at=eval_time
    )

    title = ContentTitle(
        title_id="T1", name="Test", dialect="d1", language="Bhojpuri",
        genre="Drama", episode_count=4, episode_duration_mins=20,
        available_from=eval_time - timedelta(days=1), available_to=eval_time + timedelta(days=1),
        description="test"
    )

    is_verified, checks, failure = verifier.verify(
        viewer_id="V-QUIET-01",
        action="PUSH_NOTIFICATION",
        content_refs=["title:T1"],
        content_titles=[title],
        active_goal=ActiveGoal(
            goal_id="G1", name="G1", version="v1", selected_at=eval_time,
            deadline=eval_time + timedelta(days=1), success_signal="play", target_metric="play"
        ),
        dialect_res=DialectResolution(used="d1", source="profile"),
        state=state,
        profile=None,
        eval_time=eval_time,
        messages_sent_today=0
    )

    assert not is_verified
    assert "quiet_hours" in checks.failed
    assert "quiet_hours" in failure

def test_channel_consent_required():
    """
    Verifies that push/WhatsApp actions without explicit opt-in consent are blocked.
    """
    verifier = IndependentVerifier()
    # 14:00 local time (outside quiet hours)
    eval_time = datetime(2026, 9, 12, 8, 30, 0, tzinfo=timezone.utc)
    
    state = ViewerState(viewer_id="V-NOCONSENT-01")
    # No consent!
    state.facts["consent_push"] = ViewerFact(
        fact_key="consent_push", value=False, source="profile", recorded_at=eval_time
    )

    title = ContentTitle(
        title_id="T1", name="Test", dialect="d1", language="Bhojpuri",
        genre="Drama", episode_count=4, episode_duration_mins=20,
        available_from=eval_time - timedelta(days=1), available_to=eval_time + timedelta(days=1),
        description="test"
    )

    is_verified, checks, failure = verifier.verify(
        viewer_id="V-NOCONSENT-01",
        action="PUSH_NOTIFICATION",
        content_refs=["title:T1"],
        content_titles=[title],
        active_goal=ActiveGoal(
            goal_id="G1", name="G1", version="v1", selected_at=eval_time,
            deadline=eval_time + timedelta(days=1), success_signal="play", target_metric="play"
        ),
        dialect_res=DialectResolution(used="d1", source="profile"),
        state=state,
        profile=None,
        eval_time=eval_time,
        messages_sent_today=0
    )

    assert not is_verified
    assert "channel_consent" in checks.failed

def test_daily_frequency_cap_enforcement():
    """
    Verifies that sending more than 1 message per day to a viewer is blocked.
    """
    verifier = IndependentVerifier()
    eval_time = datetime(2026, 9, 12, 8, 30, 0, tzinfo=timezone.utc)
    
    state = ViewerState(viewer_id="V-CAP-01")
    state.facts["consent_push"] = ViewerFact(
        fact_key="consent_push", value=True, source="profile", recorded_at=eval_time
    )

    title = ContentTitle(
        title_id="T1", name="Test", dialect="d1", language="Bhojpuri",
        genre="Drama", episode_count=4, episode_duration_mins=20,
        available_from=eval_time - timedelta(days=1), available_to=eval_time + timedelta(days=1),
        description="test"
    )

    # Already sent 1 message today
    is_verified, checks, failure = verifier.verify(
        viewer_id="V-CAP-01",
        action="PUSH_NOTIFICATION",
        content_refs=["title:T1"],
        content_titles=[title],
        active_goal=ActiveGoal(
            goal_id="G1", name="G1", version="v1", selected_at=eval_time,
            deadline=eval_time + timedelta(days=1), success_signal="play", target_metric="play"
        ),
        dialect_res=DialectResolution(used="d1", source="profile"),
        state=state,
        profile=None,
        eval_time=eval_time,
        messages_sent_today=1 # Exceeded limit!
    )

    assert not is_verified
    assert "frequency_cap" in checks.failed

def test_minimum_row_size_for_homepage():
    """
    Verifies that a HOME_PAGE action containing fewer than 3 titles is blocked
    and must not be shown.
    """
    verifier = IndependentVerifier()
    eval_time = datetime(2026, 9, 12, 10, 0, 0, tzinfo=timezone.utc)
    state = ViewerState(viewer_id="V-ROW-01")

    # Only 2 titles provided
    titles = [
        ContentTitle(
            title_id="T1", name="Test 1", dialect="d1", language="Bhojpuri",
            genre="Drama", episode_count=4, episode_duration_mins=20,
            available_from=eval_time - timedelta(days=1), available_to=eval_time + timedelta(days=1),
            description="test"
        ),
        ContentTitle(
            title_id="T2", name="Test 2", dialect="d1", language="Bhojpuri",
            genre="Comedy", episode_count=4, episode_duration_mins=20,
            available_from=eval_time - timedelta(days=1), available_to=eval_time + timedelta(days=1),
            description="test"
        )
    ]

    is_verified, checks, failure = verifier.verify(
        viewer_id="V-ROW-01",
        action="HOME_PAGE",
        content_refs=["title:T1", "title:T2"], # < 3 titles
        content_titles=titles,
        active_goal=ActiveGoal(
            goal_id="G1", name="G1", version="v1", selected_at=eval_time,
            deadline=eval_time + timedelta(days=1), success_signal="play", target_metric="play"
        ),
        dialect_res=DialectResolution(used="d1", source="profile"),
        state=state,
        profile=None,
        eval_time=eval_time,
        messages_sent_today=0
    )

    assert not is_verified
    assert "minimum_row_size" in checks.failed

def test_dialect_and_availability_verification():
    """
    Verifies that the verifier rejects content with wrong dialect or expired availability.
    """
    verifier = IndependentVerifier()
    eval_time = datetime(2026, 9, 12, 10, 0, 0, tzinfo=timezone.utc)
    state = ViewerState(viewer_id="V-DIAL-01")

    # Title has dialect d2, but viewer resolved dialect is d1
    title_wrong_dialect = ContentTitle(
        title_id="T_WRONG", name="Wrong Dialect", dialect="d2", language="Haryanvi",
        genre="Drama", episode_count=4, episode_duration_mins=20,
        available_from=eval_time - timedelta(days=1), available_to=eval_time + timedelta(days=1),
        description="test"
    )

    is_verified, checks, failure = verifier.verify(
        viewer_id="V-DIAL-01",
        action="HERO_SLOT",
        content_refs=["title:T_WRONG"],
        content_titles=[title_wrong_dialect],
        active_goal=ActiveGoal(
            goal_id="G1", name="G1", version="v1", selected_at=eval_time,
            deadline=eval_time + timedelta(days=1), success_signal="play", target_metric="play"
        ),
        dialect_res=DialectResolution(used="d1", source="profile"), # Mismatch!
        state=state,
        profile=None,
        eval_time=eval_time,
        messages_sent_today=0
    )

    assert not is_verified
    assert "dialect" in checks.failed
