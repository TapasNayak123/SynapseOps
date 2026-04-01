"""Application configuration loaded from environment variables."""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    # --- Core settings ---
    aws_region: str = "us-east-1"
    github_token: str = ""
    teams_webhook_url: str = ""
    bedrock_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    bedrock_region: str = "us-east-1"
    bedrock_backend: str = "runtime"  # runtime | agentcore
    bedrock_agent_id: str = ""
    bedrock_agent_alias_id: str = ""
    bedrock_agent_session_prefix: str = "synapseops"

    # --- PR analysis / webhook settings ---
    github_webhook_secret: str = ""
    poll_interval: int = 60
    app_base_url: str = "http://localhost:5000"

    # --- Monitoring / alerting settings ---
    cloudwatch_log_group: str = "/your/service/log-group"
    dynamodb_table_prefix: str = "synapse-ops"
    redis_url: str = "redis://localhost:6379/0"
    github_repo: str = ""
    error_rate_threshold: float = 50.0
    slow_api_threshold_ms: int = 2000
    monitoring_interval_seconds: int = 60
    alert_cooldown_minutes: int = 60
    monitored_apis: str = ""
    chat_rate_limit_per_minute: int = 30
    monitor_branch: str = ""

    @field_validator("error_rate_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        if not 0 < v <= 100:
            raise ValueError("error_rate_threshold must be between 0 and 100")
        return v

    @field_validator("slow_api_threshold_ms")
    @classmethod
    def validate_slow_threshold(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("slow_api_threshold_ms must be positive")
        return v

    @field_validator("chat_rate_limit_per_minute")
    @classmethod
    def validate_rate_limit(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("chat_rate_limit_per_minute must be positive")
        return v

    @field_validator("poll_interval")
    @classmethod
    def validate_poll_interval(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("poll_interval must be positive")
        return v

    @field_validator("bedrock_backend")
    @classmethod
    def validate_bedrock_backend(cls, v: str) -> str:
        normalized = (v or "runtime").strip().lower()
        if normalized not in {"runtime", "agentcore"}:
            raise ValueError("bedrock_backend must be either 'runtime' or 'agentcore'")
        return normalized

    @property
    def github_repos_list(self) -> list[str]:
        """Parse GITHUB_REPO (comma-separated) into a list."""
        return [r.strip() for r in self.github_repo.split(",") if r.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_settings_on_startup() -> list[str]:
    """Validate critical settings at startup. Returns list of warnings."""
    import os
    warnings: list[str] = []
    s = get_settings()

    if s.cloudwatch_log_group == "/your/service/log-group":
        warnings.append("CLOUDWATCH_LOG_GROUP is still the default placeholder — monitoring will not work.")
    if not s.github_token:
        warnings.append("GITHUB_TOKEN is not set — PR analysis and webhook features will fail.")
    if not s.github_webhook_secret:
        warnings.append("GITHUB_WEBHOOK_SECRET is empty — webhook signature verification is DISABLED (insecure).")
    if not s.github_repo:
        warnings.append("GITHUB_REPO is not set — pipeline monitoring will not know which repos to watch.")
    if s.redis_url == "redis://localhost:6379/0" and os.environ.get("REDIS_URL") is None:
        warnings.append("REDIS_URL is default localhost — Redis caching will be unavailable in production.")
    return warnings
