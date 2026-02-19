"""
Configuration management using Pydantic Settings.

Environment variables take precedence over .env file.
Validates all settings at application startup.
"""

from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with validation.
    
    All settings can be overridden via environment variables.
    Example: DATABASE_URL=postgresql://... python app/main.py
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application
    app_name: str = "DocIntel API"
    app_version: str = "1.0.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True  # Auto-reload on code changes (dev only)
    
    # Database
    database_url: PostgresDsn = "postgresql+asyncpg://docintel:dev_password_change_in_prod@localhost:5432/docintel"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_echo: bool = False  # Log all SQL queries (useful for debugging)
    
    # Redis
    redis_url: RedisDsn = "redis://localhost:6379/0"
    redis_cache_ttl: int = 300  # 5 minutes default cache TTL
    
    # Security
    secret_key: str = "7b6fb6d9792e8213322a9d1f09505dbbef408f37c3218926d63109690dbc57ed"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # File Storage (local for now, S3-compatible interface later)
    upload_dir: str = "./uploads"
    max_upload_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: set[str] = {".pdf", ".docx", ".txt", ".md"}
    
    # Rate Limiting
    rate_limit_per_minute: int = 60

    # Cache settings
    cache_document_ttl: int = 300        # 5 minutes
    cache_stats_ttl: int = 60            # 1 minute (stats change often)
    cache_user_ttl: int = 600            # 10 minutes
    cache_tenant_ttl: int = 600          # 10 minutes

    # Rate limiting
    rate_limit_enabled: bool = True
    
    # Logging
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "console"

     # Observability
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "console"
    
    # Metrics
    metrics_enabled: bool = True
    
    # Error tracking (Sentry)
    sentry_dsn: str | None = None
    sentry_enabled: bool = False
    sentry_traces_sample_rate: float = 0.1
    
    # Performance monitoring
    slow_query_threshold_ms: float = 1000.0
    slow_request_threshold_ms: float = 2000.0
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Ensure environment is lowercase."""
        return v.lower()
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings instance.
    
    lru_cache ensures we only parse env vars once.
    Call this function to get settings anywhere in the app.
    """
    return Settings()


# Convenience export
settings = get_settings()