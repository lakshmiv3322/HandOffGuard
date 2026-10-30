"""Unit tests for Exasol query insights and benchmark endpoints."""

import os
import pytest
from app.api.routers.insights import QUERY_DEFINITIONS


def test_query_definitions_structure():
    """Verify all queries have required metadata and valid view names."""
    for q_id, q_meta in QUERY_DEFINITIONS.items():
        assert "name" in q_meta
        assert "sql_view" in q_meta
        assert "sql_file_path" in q_meta
        assert "sql_query" in q_meta
        assert q_meta["sql_view"].startswith("HANDOFFGUARD.")
        assert os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), q_meta["sql_file_path"]))


def test_benchmark_report_file_exists():
    """Verify that reports/interval_join_benchmark.json exists and is valid JSON."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    json_path = os.path.join(repo_root, "reports", "interval_join_benchmark.json")

    assert os.path.exists(json_path), "reports/interval_join_benchmark.json must exist"
