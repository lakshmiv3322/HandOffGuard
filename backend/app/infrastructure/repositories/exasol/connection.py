"""
Shared helpers for Exasol repository implementations.

All Exasol repos import get_pool() from here. Column names returned by
pyexasol are uppercased (Exasol normalises identifiers). Each repo is
responsible for mapping uppercase column names → domain model fields.
"""

from __future__ import annotations

from app.infrastructure.db.exasol_pool import ExasolPool, get_pool as _get_pool


def get_pool() -> ExasolPool:
    """Return the active Exasol connection pool."""
    return _get_pool()


def _ts(value):
    """
    Convert an Exasol timestamp value to a Python datetime.

    pyexasol returns timestamps as datetime.datetime objects already,
    but some configurations return strings. Handle both.
    """
    if value is None:
        return None
    if hasattr(value, "year"):
        return value
    from datetime import datetime
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return value
