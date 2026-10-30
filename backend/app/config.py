"""Application configuration loaded from environment variables via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Global application settings, sourced from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application metadata
    app_env: str = Field(default="development", description="Runtime environment")
    app_name: str = Field(default="HandoffGuard", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    debug: bool = Field(default=True, description="Enable debug mode")
    schema_version: str = Field(default="1.0.0", description="DB schema version string")

    # Database
    database_engine: str = Field(
        default="sqlite",
        description="Database engine: 'sqlite', 'postgres', or 'exasol'",
    )
    sqlite_url: str = Field(
        default="sqlite+aiosqlite:///./handoffguard_dev.db",
        description="SQLAlchemy async URL for SQLite",
    )
    postgres_url: str = Field(
        default="",
        description="SQLAlchemy async URL for PostgreSQL",
    )

    # Exasol credentials (only used when database_engine == "exasol")
    exasol_host: str = Field(default="localhost", description="Exasol host")
    exasol_port: int = Field(default=8563, description="Exasol port")
    exasol_user: str = Field(default="sys", description="Exasol user")
    exasol_password: str = Field(default="exasol", description="Exasol password")
    exasol_schema: str = Field(default="HANDOFFGUARD", description="Exasol schema")
    exasol_encryption: bool = Field(
        default=False,
        description="Enable TLS encryption for Exasol connection"
    )

    # Domain configuration
    skew_tolerance_seconds: int = Field(
        default=120,
        description="Clock-skew tolerance window applied to handoff boundaries (seconds)",
    )
    max_chart_points_per_logger: int = Field(
        default=500,
        description="Maximum temperature readings returned per logger in timeline endpoint",
    )


settings = Settings()
