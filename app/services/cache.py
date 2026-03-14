import json
import redis
import structlog
from app.config import get_settings

logger = structlog.get_logger()


class CacheService:
    def __init__(self):
        settings = get_settings()
        self.redis = redis.from_url(settings.redis_url, decode_responses=True)

    def get(self, key: str) -> dict | None:
        try:
            data = self.redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.warning("cache_get_failed", key=key, error=str(e))
            return None

    def set(self, key: str, value: dict, ttl_seconds: int = 300) -> None:
        try:
            self.redis.setex(key, ttl_seconds, json.dumps(value, default=str))
        except Exception as e:
            logger.warning("cache_set_failed", key=key, error=str(e))

    def get_last_alert_time(self, api_path: str) -> str | None:
        return self.redis.get(f"alert:last:{api_path}")

    def set_last_alert_time(self, api_path: str, timestamp: str) -> None:
        self.redis.setex(f"alert:last:{api_path}", 3600, timestamp)

    def increment_error_count(self, api_path: str, window_key: str) -> int:
        key = f"errors:{api_path}:{window_key}"
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, 3600)
        result = pipe.execute()
        return result[0]

    def get_error_count(self, api_path: str, window_key: str) -> int:
        key = f"errors:{api_path}:{window_key}"
        val = self.redis.get(key)
        return int(val) if val else 0
