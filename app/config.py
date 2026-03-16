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
