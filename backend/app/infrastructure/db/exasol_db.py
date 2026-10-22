"""
Exasol database backend placeholder.

This module provides a stub implementation of DatabaseBackend for Exasol.
Replace the NotImplementedError bodies with the real Exasol driver calls
(e.g., pyexasol or exasol-driver) when deploying to production.

Required environment variables:
  EXASOL_HOST, EXASOL_PORT, EXASOL_USER, EXASOL_PASSWORD, EXASOL_SCHEMA
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.base import DatabaseBackend


class ExasolDatabaseBackend(DatabaseBackend):
    """
    Placeholder Exasol backend.

    Production implementation should use the pyexasol driver wrapped in an
    async executor (e.g., run_in_executor) or a purpose-built async Exasol
    SQLAlchemy dialect.
    """

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        schema: str,
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._schema = schema

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:  # type: ignore[override]
        raise NotImplementedError(
            "Exasol backend is not yet implemented. "
            "Install pyexasol, wrap synchronous calls with asyncio.to_thread(), "
            "and implement the query methods in app/infrastructure/repositories/exasol/. "
            "See app/infrastructure/repositories/exasol/README.md for guidance."
        )
        yield  # make this a generator

    async def health_check(self) -> dict:
        return {
            "db_status": "error",
            "db_engine": "exasol",
            "detail": (
                "Exasol backend is not yet implemented. "
                f"Configured to connect to {self._host}:{self._port} "
                f"as {self._user} / schema {self._schema}."
            ),
        }

    async def create_tables(self) -> None:
        raise NotImplementedError(
            "Table creation for Exasol must be done via Exasol DDL scripts. "
            "The schema contract is documented in the project README."
        )
