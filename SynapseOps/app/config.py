from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    aws_region: str = "us-east-1"

    # CloudWatch
    cloudwatch_log_group: str = "/your/service/log-group"
    cloudwatch_namespace: str = "YourService"

    # DynamoDB
    dynamodb_table_prefix: str = "cw-agent"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Teams
    teams_webhook_url: str = ""

    # Bedrock
    bedrock_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    bedrock_region: str = "us-east-1"

    # Thresholds
    error_rate_threshold: float = 50.0
    slow_api_threshold_ms: int = 2000
    monitoring_interval_seconds: int = 60
    alert_cooldown_minutes: int = 60

    # GitHub (for deployment correlation)
    github_token: str = ""
    github_repo: str = ""  # e.g. "org/repo-name"

    # Monitored APIs (comma-separated, loaded into Redis on startup)
    monitored_apis: str = ""  # e.g. "/api/users,/api/orders,/api/payments"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
