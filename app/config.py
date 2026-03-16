"""Application configuration loaded from environment variables."""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    aws_region: str = "us-east-1"
    cloudwatch_log_group: str = "/your/service/log-group"
    dynamodb_table_prefix: str = "synapse-ops"
    redis_url: str = "redis://localhost:6379/0"
    teams_webhook_url: str = ""
    bedrock_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    bedrock_region: str = "us-east-1"
    error_rate_threshold: float = 50.0
    slow_api_threshold_ms: int = 2000
    monitoring_interval_seconds: int = 60
    alert_cooldown_minutes: int = 60
    github_token: str = ""
    github_repo: str = ""
    monitored_apis: str = ""
    chat_rate_limit_per_minute: int = 30

    @field_validator("error_rate_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        if not 0 < v <= 100:
            raise ValueError("error_rate_threshold must be between 0 and 100")
        return v

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
