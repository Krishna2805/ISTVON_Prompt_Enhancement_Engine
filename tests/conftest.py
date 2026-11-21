# tests/conftest.py
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path, monkeypatch):
    """Run every test in a temp dir so the relative JSON log files
    (rule_engine_logs.json, istvon_transformations_log.json) never touch the real ones."""
    monkeypatch.chdir(tmp_path)
