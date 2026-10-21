"""
Event deduplicator: computes idempotency keys, detects duplicates and out-of-order arrivals.
"""
import hashlib
from typing import Set
from src.models import Event
from src.storage.state_store import StateStore

class EventDeduplicator:
    def __init__(self, state_store: StateStore):
        self.state_store = state_store
        self._seen_event_ids: Set[str] = set()

    @staticmethod
    def compute_idempotency_key(event: Event) -> str:
        # Key based on viewer_id, event_id, event_type, timestamp
        raw = f"{event.viewer_id}:{event.event_id}:{event.event_type}:{event.timestamp.isoformat()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def is_duplicate(self, event: Event) -> bool:
        if event.event_id in self._seen_event_ids:
            return True
        if self.state_store.is_event_processed(event.event_id):
            self._seen_event_ids.add(event.event_id)
            return True
        return False

    def mark_seen(self, event: Event):
        self._seen_event_ids.add(event.event_id)
        idempotency_key = self.compute_idempotency_key(event)
        self.state_store.mark_event_processed(
            event_id=event.event_id,
            viewer_id=event.viewer_id,
            event_type=event.event_type,
            received_at=event.received_at,
            idempotency_key=idempotency_key
        )
