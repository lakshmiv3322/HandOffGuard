"""
Exasol connection pool for HandoffGuard.

Wraps the synchronous pyexasol driver in asyncio.to_thread so it can
be used from async FastAPI route handlers without blocking the event loop.

Design:
- One persistent connection per process (suitable for Exasol Personal / demo).
- Retry logic for transient ExasolConnectionError (3 attempts, 0.5 s backoff).
- Clear error messages that distinguish connection failures from query errors.
- Schema is validated on first connection.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

# pyexasol is an optional dependency; import lazily so SQLite mode still works.
try:
    import pyexasol  # type: ignore
    PYEXASOL_AVAILABLE = True
except ImportError:
    PYEXASOL_AVAILABLE = False
    pyexasol = None  # type: ignore


class ExasolConnectionError(RuntimeError):
    """Raised when a connection to Exasol cannot be established."""


class ExasolQueryError(RuntimeError):
    """Raised when an Exasol query fails."""


class ExasolPool:
    """
    Lightweight Exasol connection holder.

    Not a true pool — Exasol Personal is single-user and single-node.
    One persistent connection is sufficient for a hackathon demo.
    For production, replace with a proper connection pool.
    """

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        schema: str,
        encryption: bool = False,
        max_retries: int = 3,
        retry_delay_s: float = 0.5,
    ) -> None:
        if not PYEXASOL_AVAILABLE:
            raise ExasolConnectionError(
                "pyexasol is not installed. Run: pip install pyexasol"
            )
        self._dsn = f"{host}:{port}"
        self._user = user
        self._password = password
        self._schema = schema
        self._encryption = encryption
        self._max_retries = max_retries
        self._retry_delay_s = retry_delay_s
        self._conn: Optional[Any] = None

    # ------------------------------------------------------------------
    # Internal helpers (run in a thread via asyncio.to_thread)
    # ------------------------------------------------------------------

    def _connect_sync(self) -> Any:
        """Open a synchronous pyexasol connection with retry."""
        last_exc: Optional[Exception] = None
        for attempt in range(1, self._max_retries + 1):
            try:
                conn = pyexasol.connect(
                    dsn=self._dsn,
                    user=self._user,
                    password=self._password,
                    schema=self._schema,
                    websocket_sslopt={"cert_reqs": 0} if not self._encryption else {},
                )
                logger.info(
                    "Exasol connection established to %s (schema=%s)", self._dsn, self._schema
                )
                return conn
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Exasol connection attempt %d/%d failed: %s",
                    attempt, self._max_retries, exc
                )
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay_s)
        raise ExasolConnectionError(
            f"Could not connect to Exasol at {self._dsn} after {self._max_retries} attempts. "
            f"Last error: {last_exc}"
        )

    def _execute_sync(self, sql: str, params: Optional[dict] = None) -> list[dict]:
        """Execute a query and return all rows as dicts."""
        if self._conn is None:
            self._conn = self._connect_sync()
        try:
            stmt = self._conn.execute(sql, params or {})
            return stmt.fetchall()
        except Exception as exc:
            # Connection may have been dropped; try to reconnect once
            logger.warning("Query failed (%s); attempting reconnect.", exc)
            try:
                self._conn = self._connect_sync()
                stmt = self._conn.execute(sql, params or {})
                return stmt.fetchall()
            except Exception as exc2:
                raise ExasolQueryError(f"Exasol query error: {exc2}\nSQL: {sql}") from exc2

    def _execute_many_sync(self, sql: str, rows: list[dict]) -> None:
        """Execute an import/insert for multiple rows."""
        if self._conn is None:
            self._conn = self._connect_sync()
        try:
            self._conn.import_from_iterable(rows, (self._schema, sql))
        except Exception as exc:
            raise ExasolQueryError(f"Exasol bulk import error: {exc}") from exc

    def _health_sync(self) -> dict:
        """Return connection health info (table counts, latest reading)."""
        if self._conn is None:
            self._conn = self._connect_sync()
        result: dict = {
            "db_status": "ok",
            "db_engine": "exasol",
            "dsn": self._dsn,
            "schema": self._schema,
            "detail": "Connected",
        }
        table_counts: dict = {}
        for table in [
            "products", "shipments", "handoffs",
            "logger_devices", "logger_readings", "excursions",
        ]:
            try:
                rows = self._conn.execute(
                    f"SELECT COUNT(*) AS cnt FROM HANDOFFGUARD.{table}"
                ).fetchall()
                table_counts[table] = rows[0]["CNT"] if rows else 0
            except Exception:
                table_counts[table] = -1
        result["table_counts"] = table_counts

        # Latest reading timestamp
        try:
            rows = self._conn.execute(
                "SELECT MAX(reading_at_utc) AS latest "
                "FROM HANDOFFGUARD.logger_readings"
            ).fetchall()
            result["latest_reading_utc"] = str(rows[0]["LATEST"]) if rows and rows[0]["LATEST"] else None
        except Exception:
            result["latest_reading_utc"] = None

        return result

    def _close_sync(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    # ------------------------------------------------------------------
    # Async public API
    # ------------------------------------------------------------------

    async def execute(self, sql: str, params: Optional[dict] = None) -> list[dict]:
        """Execute SQL and return rows as list of dicts (async)."""
        return await asyncio.to_thread(self._execute_sync, sql, params)

    async def execute_many(self, sql: str, rows: list[dict]) -> None:
        """Bulk-insert rows (async)."""
        await asyncio.to_thread(self._execute_many_sync, sql, rows)

    async def health(self) -> dict:
        """Return health dict (async)."""
        return await asyncio.to_thread(self._health_sync)

    async def close(self) -> None:
        """Close the connection (async)."""
        await asyncio.to_thread(self._close_sync)


# Module-level singleton — initialised by ExasolDatabaseBackend on startup.
_pool: Optional[ExasolPool] = None


def get_pool() -> ExasolPool:
    """Return the module-level pool (must be initialised first)."""
    if _pool is None:
        raise ExasolConnectionError(
            "Exasol pool has not been initialised. "
            "Call init_pool() during application startup."
        )
    return _pool


def init_pool(
    host: str,
    port: int,
    user: str,
    password: str,
    schema: str,
    encryption: bool = False,
) -> ExasolPool:
    """Initialise (or re-use) the module-level pool."""
    global _pool
    if _pool is None:
        _pool = ExasolPool(
            host=host,
            port=port,
            user=user,
            password=password,
            schema=schema,
            encryption=encryption,
        )
    return _pool
