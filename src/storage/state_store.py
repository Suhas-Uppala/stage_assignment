"""
StateStore: persistence and retrieval layer for per-viewer agent state.
"""
import json
import os
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional
from src.models import (
    ViewerState, DecisionRecord, ActionRecord, OutcomeRecord, ActiveGoal
)
from src.storage.database import Database

class StateStore:
    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()
        self._lock = threading.Lock()

    def get_viewer_state(self, viewer_id: str) -> ViewerState:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT state_json, version FROM viewer_state WHERE viewer_id = ?", (viewer_id,))
            row = cursor.fetchone()
            if row:
                data = json.loads(row["state_json"])
                state = ViewerState.model_validate(data)
                state.version = row["version"]
                return state
            else:
                return ViewerState(viewer_id=viewer_id, version=1)

    def save_viewer_state(self, state: ViewerState) -> bool:
        with self._lock:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                state_json = state.model_dump_json()
                new_version = state.version + 1
                cursor.execute("""
                    INSERT INTO viewer_state (viewer_id, state_json, version, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(viewer_id) DO UPDATE SET
                        state_json = excluded.state_json,
                        version = excluded.version,
                        updated_at = CURRENT_TIMESTAMP
                """, (state.viewer_id, state_json, new_version))
                conn.commit()
                state.version = new_version
                return True

    def record_decision(self, decision: DecisionRecord) -> bool:
        with self._lock:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO decisions (decision_id, viewer_id, idempotency_key, action, status, decision_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    decision.decision_id,
                    decision.viewer_id,
                    decision.idempotency_key or decision.decision_id,
                    decision.action,
                    decision.status,
                    decision.model_dump_json()
                ))
                conn.commit()
                return cursor.rowcount > 0

    def get_decision_by_idempotency(self, idempotency_key: str) -> Optional[DecisionRecord]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT decision_json FROM decisions WHERE idempotency_key = ?", (idempotency_key,))
            row = cursor.fetchone()
            if row:
                return DecisionRecord.model_validate_json(row["decision_json"])
            return None

    def record_action(self, action: ActionRecord) -> bool:
        with self._lock:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO actions (action_id, decision_id, viewer_id, idempotency_key, action_type, status, action_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    action.action_id,
                    action.decision_id,
                    action.viewer_id,
                    action.idempotency_key,
                    action.action_type,
                    action.status,
                    action.model_dump_json()
                ))
                conn.commit()
                return cursor.rowcount > 0

    def record_outcome(self, outcome: OutcomeRecord) -> bool:
        with self._lock:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO outcomes (outcome_id, decision_id, viewer_id, goal_id, classification, outcome_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    outcome.outcome_id,
                    outcome.decision_id,
                    outcome.viewer_id,
                    outcome.goal_id,
                    outcome.classification,
                    outcome.model_dump_json()
                ))
                conn.commit()
                return True

    def mark_event_processed(self, event_id: str, viewer_id: str, event_type: str, received_at: datetime, idempotency_key: Optional[str] = None):
        with self._lock:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO processed_events (event_id, viewer_id, event_type, received_at, idempotency_key)
                    VALUES (?, ?, ?, ?, ?)
                """, (event_id, viewer_id, event_type, received_at.isoformat(), idempotency_key))
                conn.commit()

    def is_event_processed(self, event_id: str) -> bool:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM processed_events WHERE event_id = ?", (event_id,))
            return cursor.fetchone() is not None

    def get_all_decisions(self) -> List[DecisionRecord]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT decision_json FROM decisions ORDER BY created_at ASC")
            return [DecisionRecord.model_validate_json(row["decision_json"]) for row in cursor.fetchall()]

    def get_all_actions(self) -> List[ActionRecord]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT action_json FROM actions ORDER BY executed_at ASC")
            return [ActionRecord.model_validate_json(row["action_json"]) for row in cursor.fetchall()]

    def get_all_outcomes(self) -> List[OutcomeRecord]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT outcome_json FROM outcomes ORDER BY evaluated_at ASC")
            return [OutcomeRecord.model_validate_json(row["outcome_json"]) for row in cursor.fetchall()]

    def export_artifacts(self, export_dir: str = "sample_run"):
        os.makedirs(export_dir, exist_ok=True)
        viewer_state_dir = os.path.join(export_dir, "viewer_state")
        os.makedirs(viewer_state_dir, exist_ok=True)

        # 1. Export viewer state files
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT viewer_id, state_json FROM viewer_state")
            for row in cursor.fetchall():
                v_path = os.path.join(viewer_state_dir, f"{row['viewer_id']}.json")
                with open(v_path, 'w', encoding='utf-8') as f:
                    # pretty format
                    parsed = json.loads(row["state_json"])
                    json.dump(parsed, f, indent=2)

        # 2. Export decisions.jsonl
        decisions_path = os.path.join(export_dir, "decisions.jsonl")
        with open(decisions_path, 'w', encoding='utf-8') as f:
            for d in self.get_all_decisions():
                f.write(d.model_dump_json() + '\n')

        # 3. Export actions.jsonl
        actions_path = os.path.join(export_dir, "actions.jsonl")
        with open(actions_path, 'w', encoding='utf-8') as f:
            for a in self.get_all_actions():
                f.write(a.model_dump_json() + '\n')

        # 4. Export outcomes.jsonl
        outcomes_path = os.path.join(export_dir, "outcomes.jsonl")
        with open(outcomes_path, 'w', encoding='utf-8') as f:
            for o in self.get_all_outcomes():
                f.write(o.model_dump_json() + '\n')
