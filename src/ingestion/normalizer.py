"""
Event normalizer: validation, timestamp parsing, event age computation, and staleness detection.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from src.config import CONFIG
from src.models import Event

class EventNormalizer:
    @staticmethod
    def parse_datetime(dt_val: Any) -> datetime:
        if isinstance(dt_val, datetime):
            if dt_val.tzinfo is None:
                return dt_val.replace(tzinfo=timezone.utc)
            return dt_val
        if isinstance(dt_val, (int, float)):
            return datetime.fromtimestamp(dt_val, tz=timezone.utc)
        if isinstance(dt_val, str):
            # Clean ISO string
            s = dt_val.replace('Z', '+00:00')
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        raise ValueError(f"Unsupported datetime format: {dt_val}")

    @classmethod
    def normalize(cls, raw: Dict[str, Any]) -> Tuple[Optional[Event], Optional[str]]:
        try:
            event_id = str(raw.get("event_id") or "")
            viewer_id = str(raw.get("viewer_id") or "")
            event_type = str(raw.get("event_type") or "")
            
            if not event_id or not viewer_id or not event_type:
                return None, "malformed_event:missing_mandatory_keys"

            ts_raw = raw.get("timestamp")
            rec_raw = raw.get("received_at")
            
            if not ts_raw:
                return None, "malformed_event:missing_timestamp"
            
            timestamp = cls.parse_datetime(ts_raw)
            received_at = cls.parse_datetime(rec_raw) if rec_raw else datetime.now(timezone.utc)
            
            event = Event(
                event_id=event_id,
                viewer_id=viewer_id,
                event_type=event_type,
                timestamp=timestamp,
                received_at=received_at,
                payload=raw.get("payload", {})
            )
            event.calculate_age()
            return event, None
        except Exception as e:
            return None, f"malformed_event:{str(e)}"
