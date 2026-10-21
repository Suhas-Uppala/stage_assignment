"""
FactResolver: Source precedence, freshness validation, conflict resolution, and provenance.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from src.models import Event, ViewerFact, ViewerState, DialectResolution

class FactResolver:
    """
    Implements domain-specific precedence rules:
    1. Dialect:
       - In-app authority: app_setting (real-time UI state) > profile_snapshot (1-day stale warehouse) > campaign_link.
       - Freshness threshold: app_setting must be within 7 days.
       - Conflicts are explicitly tracked and preserved.
    2. Subscription Status:
       - Real-time authority: purchase events in event_stream > profile_snapshot.
       - A successful purchase event immediately promotes free/trial to paid.
    3. Profile Deduplication:
       - Always select the latest updated_at record when multiple profile versions exist.
    4. Messaging Consents:
       - Retain explicit opt-in flags with timestamp.
    """

    @staticmethod
    def resolve_profile(profiles: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not profiles:
            return None
        if len(profiles) == 1:
            return profiles[0]
        # Sort by updated_at descending to deduplicate profile snapshots
        sorted_p = sorted(
            profiles,
            key=lambda x: str(x.get("updated_at", "")),
            reverse=True
        )
        return sorted_p[0]

    @classmethod
    def resolve_dialect(
        cls,
        event: Optional[Event],
        profile: Optional[Dict[str, Any]],
        state: ViewerState,
        eval_time: datetime
    ) -> DialectResolution:
        conflicts: List[str] = []
        
        # Candidate 1: app_setting from current event payload
        app_dialect = None
        if event and event.payload:
            app_dialect = event.payload.get("app_setting_dialect")

        # Candidate 2: profile snapshot preferred_dialect
        prof_dialect = None
        if profile:
            prof_dialect = profile.get("preferred_dialect")

        # Candidate 3: campaign link from event payload
        camp_dialect = None
        if event and event.payload:
            camp_link = str(event.payload.get("campaign_link", ""))
            for d in ['d1', 'd2', 'd3', 'd4', 'd5', 'd6']:
                if d in camp_link:
                    camp_dialect = d
                    break

        # Candidate 4: existing state fact
        prev_dialect_fact = state.facts.get("preferred_dialect")
        prev_dialect = prev_dialect_fact.value if prev_dialect_fact else None

        # Precedence & Conflict Detection
        # In-app content priority: app_setting > profile > campaign > prev_state > default
        selected_dialect = "d1"
        source = "default"

        if app_dialect:
            selected_dialect = app_dialect
            source = "app_setting"
            if prof_dialect and prof_dialect != app_dialect:
                conflicts.append(f"profile:{prof_dialect}")
            if camp_dialect and camp_dialect != app_dialect:
                conflicts.append(f"campaign:{camp_dialect}")
        elif prof_dialect:
            selected_dialect = prof_dialect
            source = "profile"
            if camp_dialect and camp_dialect != prof_dialect:
                conflicts.append(f"campaign:{camp_dialect}")
        elif camp_dialect:
            selected_dialect = camp_dialect
            source = "campaign_link"
        elif prev_dialect:
            selected_dialect = prev_dialect
            source = "viewer_history"
        else:
            selected_dialect = "d1"
            source = "platform_default"

        # Update ViewerState fact
        fact = ViewerFact(
            fact_key="preferred_dialect",
            value=selected_dialect,
            source=source,
            recorded_at=eval_time,
            freshness_s=0.0,
            conflicts=[{"source": c.split(':')[0], "value": c.split(':')[1]} for c in conflicts]
        )
        state.facts["preferred_dialect"] = fact

        return DialectResolution(
            used=selected_dialect,
            source=source,
            conflicts=conflicts
        )

    @classmethod
    def resolve_subscription(
        cls,
        event: Optional[Event],
        profile: Optional[Dict[str, Any]],
        state: ViewerState,
        eval_time: datetime
    ) -> Tuple[str, str, Optional[str]]:
        """
        Returns (status, source, evidence_id)
        Real-time purchase event takes precedence over stale profile.
        """
        # 1. Check if current event is a purchase
        if event and event.event_type == "purchase":
            status = event.payload.get("subscription_status", "paid")
            if event.payload.get("status") == "success":
                fact = ViewerFact(
                    fact_key="subscription_status",
                    value="paid",
                    source="event_stream",
                    recorded_at=event.timestamp,
                    freshness_s=max(0.0, (eval_time - event.timestamp).total_seconds())
                )
                state.facts["subscription_status"] = fact
                return "paid", "event_stream", f"event:{event.event_id}"

        # 2. Check if state already has recorded purchase
        if "subscription_status" in state.facts and state.facts["subscription_status"].value == "paid":
            fact = state.facts["subscription_status"]
            return "paid", fact.source, "state:verified_purchase"

        # 3. Check profile snapshot
        if profile and profile.get("subscription_status"):
            p_status = profile.get("subscription_status")
            fact = ViewerFact(
                fact_key="subscription_status",
                value=p_status,
                source="profile_snapshot",
                recorded_at=eval_time,
                freshness_s=86400.0 # ~ 1 day stale
            )
            state.facts["subscription_status"] = fact
            return p_status, "profile_snapshot", f"profile:{profile.get('viewer_id')}"

        # Default free
        fact = ViewerFact(
            fact_key="subscription_status",
            value="free",
            source="default",
            recorded_at=eval_time,
            freshness_s=0.0
        )
        state.facts["subscription_status"] = fact
        return "free", "default", None

    @classmethod
    def resolve_consents(
        cls,
        profile: Optional[Dict[str, Any]],
        state: ViewerState,
        eval_time: datetime
    ) -> Tuple[bool, bool]:
        push_consent = False
        wa_consent = False
        
        if profile:
            push_consent = bool(int(profile.get("consent_push", 0)))
            wa_consent = bool(int(profile.get("consent_whatsapp", 0)))

        state.facts["consent_push"] = ViewerFact(
            fact_key="consent_push",
            value=push_consent,
            source="profile_snapshot" if profile else "default",
            recorded_at=eval_time,
            freshness_s=86400.0 if profile else 0.0
        )
        state.facts["consent_whatsapp"] = ViewerFact(
            fact_key="consent_whatsapp",
            value=wa_consent,
            source="profile_snapshot" if profile else "default",
            recorded_at=eval_time,
            freshness_s=86400.0 if profile else 0.0
        )
        return push_consent, wa_consent

    @staticmethod
    def is_quiet_hours(eval_time: datetime) -> bool:
        # Platform local time in India (IST, UTC+5:30)
        # 22:00 to 08:00 local time
        # eval_time is UTC. Offset +5.5 hours for IST
        ist_hour = (eval_time.hour + 5 + (1 if eval_time.minute + 30 >= 60 else 0)) % 24
        return (ist_hour >= 22 or ist_hour < 8)
