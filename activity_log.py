"""Centralized activity log for agent events. Thread-safe, in-memory."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class LogEntry:
    agent: str
    event: str          # started | processing | completed | error
    message: str
    repo: str = ""
    pr_number: int = 0
    duration_ms: int = 0
    timestamp: float = field(default_factory=time.time)


class ActivityLog:
    """Append-only log with a max size cap."""

    MAX_ENTRIES = 500

    def __init__(self):
        self._entries: list[LogEntry] = []
        self._lock = threading.Lock()
        self._counter = 0  # monotonic id for polling "since"

    def emit(self, agent: str, event: str, message: str, *,
             repo: str = "", pr_number: int = 0, duration_ms: int = 0):
        entry = LogEntry(
            agent=agent, event=event, message=message,
            repo=repo, pr_number=pr_number, duration_ms=duration_ms,
        )
        with self._lock:
            self._counter += 1
            self._entries.append(entry)
            # Trim oldest when over cap
            if len(self._entries) > self.MAX_ENTRIES:
                self._entries = self._entries[-self.MAX_ENTRIES:]

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
        return [
            {
                "agent": e.agent,
                "event": e.event,
                "message": e.message,
                "repo": e.repo,
                "pr_number": e.pr_number,
                "duration_ms": e.duration_ms,
                "timestamp": e.timestamp,
            }
            for e in items
        ]


# Global singleton
activity_log = ActivityLog()
