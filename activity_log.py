"""Centralized activity log — persisted to DynamoDB, cached in-memory for fast polling."""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal


@dataclass
class LogEntry:
    agent: str
    event: str          # started | processing | completed | error
    message: str
    repo: str = ""
    pr_number: int = 0
    duration_ms: int = 0
    timestamp: float = field(default_factory=time.time)


def _entry_to_dict(e: LogEntry) -> dict:
    return {
        "agent": e.agent, "event": e.event, "message": e.message,
        "repo": e.repo, "pr_number": e.pr_number,
        "duration_ms": e.duration_ms, "timestamp": e.timestamp,
    }


class ActivityLog:
    """Append-only activity log backed by DynamoDB with in-memory cache."""

    MAX_MEMORY = 500  # in-memory cap for fast polling

    def __init__(self):
        self._entries: list[LogEntry] = []
        self._lock = threading.Lock()
        self._counter = 0
        self._loop = None
        self._db_table = None
        self._db_ready = False
        self._loaded = False
        # Init DynamoDB in background to not slow down import
        threading.Thread(target=self._init_db, daemon=True).start()

    def _init_db(self):
        """Connect to DynamoDB audit table for persistence."""
        try:
            from app.services.dynamodb import _get_resource
            from app.config import get_settings
            prefix = get_settings().dynamodb_table_prefix
            self._db_table = _get_resource().Table(f"{prefix}-audit")
            self._db_table.table_status  # verify it exists
            self._db_ready = True
            # Load recent entries from DynamoDB into memory
            self._load_recent()
        except Exception:
            self._db_ready = False

    def _load_recent(self):
        """Load last 24h of activity from DynamoDB into memory on startup."""
        if self._loaded or not self._db_ready:
            return
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
            entries = []
            for day in [yesterday, today]:
                resp = self._db_table.query(
                    KeyConditionExpression="pk = :pk",
                    ExpressionAttributeValues={":pk": f"ACTIVITY#{day}"},
                    ScanIndexForward=True, Limit=250,
                )
                for item in resp.get("Items", []):
                    entries.append(LogEntry(
                        agent=item.get("agent", ""),
                        event=item.get("event", ""),
                        message=item.get("message", ""),
                        repo=item.get("repo", ""),
                        pr_number=int(item.get("pr_number", 0)),
                        duration_ms=int(item.get("duration_ms", 0)),
                        timestamp=float(item.get("timestamp", 0)),
                    ))
            if entries:
                with self._lock:
                    self._entries = entries[-self.MAX_MEMORY:]
                    self._counter = len(self._entries)
            self._loaded = True
        except Exception:
            pass  # Degrade gracefully

    def emit(self, agent: str, event: str, message: str, *,
             repo: str = "", pr_number: int = 0, duration_ms: int = 0):
        entry = LogEntry(
            agent=agent, event=event, message=message,
            repo=repo, pr_number=pr_number, duration_ms=duration_ms,
        )
        with self._lock:
            self._counter += 1
            self._entries.append(entry)
            if len(self._entries) > self.MAX_MEMORY:
                self._entries = self._entries[-self.MAX_MEMORY:]

        # Persist to DynamoDB (fire-and-forget in background thread)
        threading.Thread(target=self._persist, args=(entry,), daemon=True).start()
        # Broadcast to WebSocket clients
        self._broadcast_to_websocket(entry)

    def _persist(self, entry: LogEntry):
        """Write a single entry to DynamoDB."""
        if not self._db_ready or not self._db_table:
            return
        try:
            day = datetime.utcfromtimestamp(entry.timestamp).strftime("%Y-%m-%d")
            ts_iso = datetime.utcfromtimestamp(entry.timestamp).isoformat()
            self._db_table.put_item(Item={
                "pk": f"ACTIVITY#{day}",
                "sk": ts_iso,
                "agent": entry.agent,
                "event": entry.event,
                "message": entry.message[:500],
                "repo": entry.repo,
                "pr_number": entry.pr_number,
                "duration_ms": entry.duration_ms,
                "timestamp": Decimal(str(round(entry.timestamp, 3))),
            })
        except Exception:
            pass  # Never break the caller

    def _broadcast_to_websocket(self, entry: LogEntry):
        """Push to WebSocket clients (non-blocking, thread-safe)."""
        try:
            from app.services.websocket_manager import get_websocket_manager
            manager = get_websocket_manager()
            if not manager.activity_connections:
                return
            event_dict = _entry_to_dict(entry)
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(manager.broadcast_activity(event_dict))
            except RuntimeError:
                if self._loop and self._loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        manager.broadcast_activity(event_dict), self._loop
                    )
        except Exception:
            pass

    def set_event_loop(self, loop):
        """Store main event loop reference for cross-thread WS broadcasting."""
        self._loop = loop

    def all(self) -> list[LogEntry]:
        with self._lock:
            return list(self._entries)

    def since(self, after_index: int) -> tuple[list[LogEntry], int]:
        """Return entries added after `after_index` and the current index."""
        with self._lock:
            total = self._counter
            count = len(self._entries)
            if after_index >= total:
                return [], total
            skip = max(0, count - (total - after_index))
            return list(self._entries[skip:]), total

    def to_dicts(self, entries: list[LogEntry] | None = None) -> list[dict]:
        items = entries if entries is not None else self.all()
        return [_entry_to_dict(e) for e in items]


# Global singleton
activity_log = ActivityLog()
