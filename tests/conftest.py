"""
Pytest configuration and shared fixtures for OTT Dialect Platform tests.
"""
import os
import sys
import shutil
import tempfile
import pytest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime, timezone
from src.config import CONFIG
from src.storage.database import Database
from src.storage.state_store import StateStore
from src.replay.orchestrator import ReplayOrchestrator


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)

@pytest.fixture
def test_db(temp_dir):
    db_path = os.path.join(temp_dir, "test_state.db")
    db = Database(db_path)
    return db

@pytest.fixture
def test_state_store(test_db):
    return StateStore(test_db)

@pytest.fixture
def test_orchestrator(temp_dir, test_db):
    orch = ReplayOrchestrator(
        db_path=test_db.db_path,
        profiles_path="data/synthetic_pack/viewer_profiles.csv",
        content_path="data/catalogue/content_catalogue.json",
        goals_path="data/catalogue/goal_catalogue.json",
        holdout_path="data/synthetic_pack/holdout_assignments.json",
        output_dir=os.path.join(temp_dir, "sample_run")
    )
    return orch
