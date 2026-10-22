# Exasol Repository Implementations

This directory contains placeholder stubs for Exasol-backed repository implementations.

## How to implement

1. **Install the Exasol driver:**
   ```bash
   pip install pyexasol
   ```

2. **Create one file per repository interface** (mirroring `app/infrastructure/repositories/dev/`):
   - `shipment_repo.py` → implements `AbstractShipmentRepository`
   - `handoff_repo.py` → implements `AbstractHandoffRepository`
   - `logger_repo.py` → implements `AbstractLoggerRepository`
   - `reading_repo.py` → implements `AbstractReadingRepository`
   - `excursion_repo.py` → implements `AbstractExcursionRepository`
   - `attribution_repo.py` → implements `AbstractAttributionRepository`

3. **Connection pattern** (synchronous pyexasol wrapped in `asyncio.to_thread`):
   ```python
   import asyncio
   import pyexasol
   from app.config import settings

   async def _run_query(sql: str, params: dict) -> list[dict]:
       def _sync():
           conn = pyexasol.connect(
               dsn=f"{settings.exasol_host}:{settings.exasol_port}",
               user=settings.exasol_user,
               password=settings.exasol_password,
               schema=settings.exasol_schema,
           )
           stmt = conn.execute(sql, params)
           return stmt.fetchall()
       return await asyncio.to_thread(_sync)
   ```

4. **Register implementations in `app/api/deps.py`** under the `"exasol"` branch.

## Schema reference

All Exasol table definitions are documented in the project root README and mirror
the SQLAlchemy ORM models in `app/infrastructure/db/dev_db.py`.

## Important constraints

- `temperature_readings` has **no** `handoff_id` column.
- All timestamps are stored as UTC and must be returned as timezone-naive `datetime` objects
  (the application treats all datetimes as UTC-implicitly).
- Use `EXASOL_SCHEMA.table_name` qualification in all SQL queries.
