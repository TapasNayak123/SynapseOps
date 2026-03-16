"""In-memory store for processed PR data. Swap with DynamoDB for production."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class AgentResult:
    name: str
    output: str
    duration_ms: int

@dataclass
class PRRecord:
    repo: str
    pr_number: int
    title: str
    author: str
    branch: str
    target: str
    action: str
    summary: str
    risk_level: str
    pr_type: str = "Unknown"
    priority: str = "Medium"
    agent_results: list[AgentResult] = field(default_factory=list)
    total_duration_ms: int = 0
    files_changed: int = 0
    additions: int = 0
    deletions: int = 0
    timestamp: float = field(default_factory=time.time)


class PRStore:
    """Simple in-memory store. Thread-safe enough for a POC."""

    def __init__(self):
        self._records: list[PRRecord] = []

    def add(self, record: PRRecord):
        self._records.insert(0, record)  # newest first

    def all(self) -> list[PRRecord]:
        return list(self._records)

    def get(self, repo: str, pr_number: int) -> Optional[PRRecord]:
        for r in self._records:
            if r.repo == repo and r.pr_number == pr_number:
                return r
        return None

    def stats(self) -> dict:
        total = len(self._records)
        if total == 0:
            return {"total": 0, "avg_duration_ms": 0, "risk_counts": {}, "total_files": 0}

        avg_dur = sum(r.total_duration_ms for r in self._records) // total
        risk_counts = {}
        total_files = 0
        for r in self._records:
            risk_counts[r.risk_level] = risk_counts.get(r.risk_level, 0) + 1
            total_files += r.files_changed

        return {
            "total": total,
            "avg_duration_ms": avg_dur,
            "risk_counts": risk_counts,
            "total_files": total_files,
        }


# Global singleton
pr_store = PRStore()
