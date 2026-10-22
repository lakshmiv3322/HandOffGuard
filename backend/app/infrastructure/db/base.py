"""
Abstract database interface.

Concrete implementations (SQLite/SQLAlchemy, Exasol) subclass DatabaseBackend
and provide an async SQLAlchemy engine plus a health-check method.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession


class DatabaseBackend(ABC):
    """Abstract base for all database backend implementations."""

    @abstractmethod
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Yield an async SQLAlchemy session."""
        ...

    @abstractmethod
    async def health_check(self) -> dict:
        """
        Return a dict with at least:
          {
              "db_status": "ok" | "error",
              "db_engine": "<engine name>",
              "detail": "<optional human-readable message>"
          }
        """
        ...

    @abstractmethod
    async def create_tables(self) -> None:
        """Create all ORM-mapped tables (idempotent). Used for dev/test only."""
        ...
