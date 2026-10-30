"""
Exasol database backend — real implementation using pyexasol.

Replaces the placeholder stub. Uses ExasolPool (see exasol_pool.py)
to manage a persistent synchronous connection wrapped in asyncio.to_thread.
"""

from __future__ import annotations

from app.infrastructure.db.base import DatabaseBackend
from app.infrastructure.db.exasol_pool import (
    ExasolConnectionError,
    ExasolPool,
    init_pool,
)


class ExasolDatabaseBackend(DatabaseBackend):
    """
    Production Exasol backend for HandoffGuard.

    Initialise once during application startup (lifespan event).
    All query methods are async via asyncio.to_thread wrapping.
    """

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        schema: str,
        encryption: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._schema = schema
        self._encryption = encryption
        self._pool: ExasolPool | None = None

    async def initialise(self) -> None:
        """Create the connection pool. Call during app startup."""
        self._pool = init_pool(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            schema=self._schema,
            encryption=self._encryption,
        )

    def get_pool(self) -> ExasolPool:
        """Return the active pool. Raises if not initialised."""
        if self._pool is None:
            raise ExasolConnectionError(
                "ExasolDatabaseBackend.initialise() has not been called."
            )
        return self._pool

    async def health_check(self) -> dict:
        """Return connection health dict."""
        if self._pool is None:
            return {
                "db_status": "error",
                "db_engine": "exasol",
                "detail": (
                    "Pool not initialised. Check EXASOL_HOST / EXASOL_PORT / "
                    "EXASOL_USER / EXASOL_PASSWORD env vars."
                ),
            }
        try:
            return await self._pool.health()
        except Exception as exc:
            return {
                "db_status": "error",
                "db_engine": "exasol",
                "detail": str(exc),
            }

    async def create_tables(self) -> None:
        """
        Table creation is done via SQL migration files in db/migrations/.
        This method is a no-op for Exasol (schema managed externally).
        """
        # Intentionally a no-op — run 001–002 migration SQL manually.
        pass
