"""Redis cache service with connection pooling and rate limiting."""
import json
import redis
import structlog
from typing import Any, Optional
from app.config import get_settings

logger = structlog.get_logger()

_client: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    global _client
    if _client is None:
        pool = redis.ConnectionPool.from_url(
            get_settings().redis_url, decode_responses=True,
            max_connections=20, socket_timeout=5, socket_connect_timeout=5, retry_on_timeout=True,
        )
        _client = redis.Redis(connection_pool=pool)
    return _client


class CacheService:
    def __init__(self):
        self.r = _get_redis()

    def ping(self) -> bool:
        try:
            return self.r.ping()
        except Exception:
            return False

    def get(self, key: str) -> Any:
        try:
            data = self.r.get(key)
            return json.loads(data) if data else None
        except (redis.ConnectionError, json.JSONDecodeError):
            return None
        except Exception as e:
            logger.warning("cache_get_failed", key=key, error=str(e))
            return None

    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        try:
            self.r.setex(key, ttl_seconds, json.dumps(value, default=str))
            return True
        except Exception as e:
            logger.warning("cache_set_failed", key=key, error=str(e))
            return False

    def delete(self, key: str) -> bool:
        try:
            self.r.delete(key)
            return True
        except Exception:
            return False

    def get_last_alert_time(self, api_path: str) -> Optional[str]:
        try:
            return self.r.get(f"alert:last:{api_path}")
        except Exception:
            return None

    def set_last_alert_time(self, api_path: str, timestamp: str) -> None:
        try:
            self.r.setex(f"alert:last:{api_path}", 3600, timestamp)
        except Exception:
            pass

    def check_rate_limit(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        """Returns True if allowed, False if exceeded."""
        try:
            pipe = self.r.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            return pipe.execute()[0] <= limit
        except Exception:
            return True  # Fail open
