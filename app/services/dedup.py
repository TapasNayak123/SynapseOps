"""Webhook deduplication — prevents processing the same event twice.

Uses Redis when available (survives restarts, works across replicas).
Falls back to an in-memory bounded set when Redis is down.

Dedup keys:
  - PR events:       "dedup:pr:{repo}:{pr_number}:{head_sha}"
  - Pipeline events:  "dedup:pipe:{repo}:{run_id}"
  - Deployment gate:  "dedup:deploy:{repo}:{run_id}"
  - Webhook delivery: "dedup:delivery:{delivery_id}"
"""
from __future__ import annotations

import logging
import threading
from app.services.cache import CacheService

logger = logging.getLogger(__name__)

# TTL for dedup keys in Redis (24 hours — long enough to cover any retry window)
_DEDUP_TTL = 86400

# In-memory fallback when Redis is unavailable
_mem_set: set[str] = set()
_mem_lock = threading.Lock()
_MAX_MEM = 10000


def _mem_check_and_set(key: str) -> bool:
    """In-memory fallback. Returns True if already seen."""
    with _mem_lock:
        if key in _mem_set:
            return True
        _mem_set.add(key)
        if len(_mem_set) > _MAX_MEM:
            # Evict oldest half (set is unordered, but good enough)
            to_remove = list(_mem_set)[:_MAX_MEM // 2]
            _mem_set.difference_update(to_remove)
        return False


def is_duplicate(key: str) -> bool:
    """Check if this event key has been processed before.

    Returns True if duplicate (skip processing), False if new (proceed).
    Atomically marks the key as seen.
    """
    cache = CacheService()
    if cache.r is not None:
        try:
            # SET NX returns True if key was set (new), False if already exists (duplicate)
            was_set = cache.r.set(f"dedup:{key}", "1", nx=True, ex=_DEDUP_TTL)
            if not was_set:
                logger.info("dedup_skip: %s (Redis)", key)
                return True
            return False
        except Exception as e:
            logger.warning("dedup_redis_error: %s — falling back to memory", e)

    # Fallback to in-memory
    if _mem_check_and_set(f"dedup:{key}"):
        logger.info("dedup_skip: %s (memory)", key)
        return True
    return False


def pr_key(repo: str, pr_number: int, head_sha: str) -> str:
    """Build dedup key for a PR event."""
    return f"pr:{repo}:{pr_number}:{head_sha}"


def pipeline_key(repo: str, run_id: int) -> str:
    """Build dedup key for a pipeline failure event."""
    return f"pipe:{repo}:{run_id}"


def deploy_key(repo: str, run_id: int) -> str:
    """Build dedup key for a deployment gate event."""
    return f"deploy:{repo}:{run_id}"


def delivery_key(delivery_id: str) -> str:
    """Build dedup key from GitHub's X-GitHub-Delivery header."""
    return f"delivery:{delivery_id}"
