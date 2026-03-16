"""Redis cache service with connection pooling and rate limiting."""
import json
import threading
import redis
import structlog
from typing import Any, Optional
from app.config import get_settings

logger = structlog.get_logger()

_client: Optional[redis.Redis] = None
_redis_available: bool = True
_redis_lock = threading.Lock()


def _get_redis() -> Optional[redis.Redis]:
    """Get Redis client. Returns None if Redis is unavailable."""
    global _client, _redis_available
    if not _redis_available:
        return None
    if _client is None:
        with _redis_lock:
            if not _redis_available:
                return None
            if _client is None:
                try:
                    pool = redis.ConnectionPool.from_url(
                        get_settings().redis_url, decode_responses=True,
                        max_connections=20, socket_timeout=3,
                        socket_connect_timeout=2, retry_on_timeout=True,
                    )
                    client = redis.Redis(connection_pool=pool)
                    client.ping()
                    _client = client
                    logger.info("redis_connected", url=get_settings().redis_url)
                except Exception as e:
                    logger.warning("redis_unavailable", error=str(e))
                    _redis_available = False
                    return None
    return _client


class CacheService:
    def __init__(self):
        self.r = _get_redis()

    def ping(self) -> bool:
        if self.r is None:
            return False
        try:
            return self.r.ping()
        except Exception:
            return False

    def get(self, key: str) -> Any:
        if self.r is None:
            return None
        try:
            data = self.r.get(key)
            return json.loads(data) if data else None
        except (redis.ConnectionError, json.JSONDecodeError):
            return None
        except Exception as e:
            logger.warning("cache_get_failed", key=key, error=str(e))
            return None

    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        if self.r is None:
            return False
        try:
            self.r.setex(key, ttl_seconds, json.dumps(value, default=str))
            return True
        except Exception as e:
            logger.warning("cache_set_failed", key=key, error=str(e))
            return False

    def delete(self, key: str) -> bool:
        if self.r is None:
            return False
        try:
            self.r.delete(key)
            return True
        except Exception:
            return False

    def get_last_alert_time(self, api_path: str) -> Optional[str]:
        if self.r is None:
            return None
        try:
            return self.r.get(f"alert:last:{api_path}")
        except Exception:
            return None

    def set_last_alert_time(self, api_path: str, timestamp: str) -> None:
        if self.r is None:
            return
        try:
            self.r.setex(f"alert:last:{api_path}", 3600, timestamp)
        except Exception:
            pass

    def check_rate_limit(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        """Returns True if allowed, False if exceeded. Uses atomic Lua script."""
        if self.r is None:
            return True  # Fail open when Redis unavailable
        try:
            lua = """
            local current = redis.call('INCR', KEYS[1])
            if current == 1 then
                redis.call('EXPIRE', KEYS[1], ARGV[1])
            end
            return current
            """
            result = self.r.eval(lua, 1, key, window_seconds)
            return int(result) <= limit
        except Exception:
            return True  # Fail open
