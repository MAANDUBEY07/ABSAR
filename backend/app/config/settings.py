"""Single configuration authority for API, workers and management commands."""

import math
from typing import Literal
from urllib.parse import urlsplit
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: Literal["development", "test", "staging", "production"] = "development"
    demo_mode: bool = False
    require_human_approval: bool = True
    auth_provider: Literal["local", "supabase"] = "local"
    jwt_secret: str = "development-only-change-before-sharing-32chars"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    database_url: str = "sqlite:///./opportunityos.db"
    mongodb_uri: str = ""
    mongodb_database: str = "opportunityos"
    redis_url: str = "redis://localhost:6379/0"
    jobs_eager: bool = True
    job_dispatch_mode: Literal["in_process", "celery"] = "celery"
    postgres_startup_diagnostics: bool = False
    career_checkpoint_db: str = "career-checkpoints.sqlite"
    aws_enabled: bool = False
    aws_region: str = ""
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_region: str = ""
    bedrock_model_id: str = ""
    ai_provider: Literal["deterministic", "gemini", "bedrock"] = "deterministic"
    gemini_api_key: str = ""
    gemini_model: str = ""
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    max_upload_bytes: int = Field(default=5 * 1024 * 1024, ge=1, le=5 * 1024 * 1024)
    rate_limit_per_minute: int = Field(default=120, ge=1)
    match_weights: dict[str, float] = Field(
        default_factory=lambda: dict(skills=0.4, preferences=0.25, experience=0.2, learning=0.15)
    )
    resend_api_key: str = ""
    resend_from: str = ""
    judge0_url: str = ""
    judge0_api_key: str = ""
    judge0_language_ids: dict[str, int] = Field(default_factory=dict)
    judge0_isolation_confirmed: bool = False
    sentry_dsn: str = ""
    otel_enabled: bool = False
    log_level: str = "INFO"
    discovery_feeds: list[str] = Field(default_factory=list)
    discovery_sources: list[str] = Field(default_factory=list)

    @property
    def hosted(self):
        return self.environment in {"production", "staging"}

    @model_validator(mode="after")
    def validate_contract(self):
        w = self.match_weights
        if (
            set(w) != {"skills", "preferences", "experience", "learning"}
            or any(not math.isfinite(v) or v < 0 for v in w.values())
            or abs(sum(w.values()) - 1) > 1e-9
        ):
            raise ValueError("MATCH_WEIGHTS requires exactly four nonnegative factors summing to 1")
        if self.auth_provider == "supabase":
            u = urlsplit(self.supabase_url)
            if (
                u.scheme != "https"
                or not u.hostname
                or u.path not in {"", "/"}
                or u.username
                or u.password
                or u.query
                or u.fragment
            ):
                raise ValueError("SUPABASE_URL must be an HTTPS project origin")
        if self.auth_provider == "cognito" and not all(
            [self.cognito_user_pool_id, self.cognito_client_id, self.cognito_region]
        ):
            raise ValueError("Cognito pool, client and region are required")
        if self.hosted:
            # Single-service hosted architectures (e.g. single Render web service) execute jobs
            # in-process via Starlette BackgroundTasks (job_dispatch_mode="in_process").
            # Limitation: in-process BackgroundTasks run in the web container and may be interrupted
            # by container restarts; this execution model is non-durable compared to detached Celery workers.
            # Multi-service hosted architectures using Celery workers require jobs_eager=False.
            if (
                self.auth_provider == "local"
                or not self.database_url.startswith("postgresql")
                or not self.mongodb_uri.startswith(("mongodb://", "mongodb+srv://"))
                or (self.job_dispatch_mode == "celery" and self.jobs_eager)
                or self.demo_mode
                or not self.require_human_approval
                or not self.redis_url.startswith(("redis://", "rediss://"))
            ):
                raise ValueError(
                    "Hosted mode requires external auth, PostgreSQL, MongoDB, Redis, durable jobs and approval"
                )
            if not self.cors_origins or any(
                urlsplit(o).scheme != "https"
                or not urlsplit(o).hostname
                or "*" in o
                or urlsplit(o).path not in {"", "/"}
                or urlsplit(o).username
                or urlsplit(o).password
                or urlsplit(o).query
                or urlsplit(o).fragment
                for o in self.cors_origins
            ):
                raise ValueError("Hosted CORS requires exact HTTPS origins")
        return self


settings = Settings()
