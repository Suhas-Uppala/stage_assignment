"""
Database schema and connection management using SQLite.
"""
import os
import sqlite3
from typing import Optional

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS viewer_state (
    viewer_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    viewer_id TEXT NOT NULL,
    idempotency_key TEXT UNIQUE NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    decision_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_decisions_viewer ON decisions(viewer_id);

CREATE TABLE IF NOT EXISTS actions (
    action_id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL,
    viewer_id TEXT NOT NULL,
    idempotency_key TEXT UNIQUE NOT NULL,
    action_type TEXT NOT NULL,
    status TEXT NOT NULL,
    action_json TEXT NOT NULL,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(decision_id) REFERENCES decisions(decision_id)
);

CREATE INDEX IF NOT EXISTS idx_actions_viewer ON actions(viewer_id);

CREATE TABLE IF NOT EXISTS outcomes (
    outcome_id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL,
    viewer_id TEXT NOT NULL,
    goal_id TEXT NOT NULL,
    classification TEXT NOT NULL,
    outcome_json TEXT NOT NULL,
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(decision_id) REFERENCES decisions(decision_id)
);

CREATE INDEX IF NOT EXISTS idx_outcomes_viewer ON outcomes(viewer_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_goal ON outcomes(goal_id);

CREATE TABLE IF NOT EXISTS processed_events (
    event_id TEXT PRIMARY KEY,
    viewer_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    received_at TIMESTAMP NOT NULL,
    idempotency_key TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

class Database:
    def __init__(self, db_path: str = "sample_run/agent_state.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
