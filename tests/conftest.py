"""
Pytest Configuration & Session Fixtures for VedioHooks AI.
Ensures strict test isolation so automated tests NEVER contaminate production jobs.db.
"""

import os
import sys
from pathlib import Path
import pytest

# Ensure workspace root in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Force all tests to run against an isolated test database
os.environ["VEDIOHOOKS_DB_PATH"] = "test_jobs.db"


@pytest.fixture(scope="session", autouse=True)
def isolated_test_database():
    """Sets up an isolated database for pytest sessions and cleans up afterwards."""
    from src.db import init_db
    from seed_existing_job import seed
    init_db()
    seed()
    yield
    # Clean up test database files
    for f in ["test_jobs.db", "test_jobs.db-wal", "test_jobs.db-shm"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass
