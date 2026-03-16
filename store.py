"""In-memory store for processed PR data. Swap with DynamoDB for production."""

from __future__ import annotations

import datetime
import threading
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
    """Thread-safe in-memory store for PR records."""

    MAX_RECORDS = 1000

    def __init__(self):
        self._records: list[PRRecord] = []
        self._lock = threading.Lock()

    def add(self, record: PRRecord):
        with self._lock:
            self._records.insert(0, record)
            if len(self._records) > self.MAX_RECORDS:
                self._records = self._records[:self.MAX_RECORDS]

    def all(self) -> list[PRRecord]:
        with self._lock:
            return list(self._records)

    def get(self, repo: str, pr_number: int) -> Optional[PRRecord]:
        with self._lock:
            for r in self._records:
                if r.repo == repo and r.pr_number == pr_number:
                    return r
            return None

    def stats(self) -> dict:
        with self._lock:
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

    def metrics(self) -> dict:
        """Compute detailed metrics for the metrics dashboard."""
        with self._lock:
            records = list(self._records)
        total = len(records)

        if total == 0:
            return {
                "total": 0, "avg_duration_ms": 0, "avg_time_saved_min": 0,
                "total_time_saved_min": 0, "total_files": 0, "total_additions": 0,
                "total_deletions": 0, "risk_counts": {}, "type_counts": {},
                "priority_counts": {}, "prs_by_date": {}, "avg_duration_by_date": {},
                "author_counts": {}, "avg_agent_durations": {},
            }

        avg_dur = sum(r.total_duration_ms for r in records) // total
        # Estimate: manual review takes ~15 min, AI takes avg_dur
        avg_saved = 15 - (avg_dur / 60000)
        if avg_saved < 0:
            avg_saved = 0

        risk_counts = {}
        type_counts = {}
        priority_counts = {}
        prs_by_date = {}
        duration_by_date = {}
        author_counts = {}
        agent_durations = {}
        total_files = 0
        total_additions = 0
        total_deletions = 0

        for r in records:
            risk_counts[r.risk_level] = risk_counts.get(r.risk_level, 0) + 1

            # Clean type/priority (strip emoji for chart labels)
            ptype = r.pr_type.split(" ", 1)[-1] if " " in r.pr_type else r.pr_type
            type_counts[ptype] = type_counts.get(ptype, 0) + 1

            pri = r.priority.split(" ", 1)[-1] if " " in r.priority else r.priority
            priority_counts[pri] = priority_counts.get(pri, 0) + 1

            day = datetime.datetime.fromtimestamp(r.timestamp).strftime("%Y-%m-%d")
            prs_by_date[day] = prs_by_date.get(day, 0) + 1
            dur_list = duration_by_date.get(day, [])
            dur_list.append(r.total_duration_ms)
            duration_by_date[day] = dur_list

            author_counts[r.author] = author_counts.get(r.author, 0) + 1
            total_files += r.files_changed
            total_additions += r.additions
            total_deletions += r.deletions

            for ar in r.agent_results:
                agent_durations.setdefault(ar.name, []).append(ar.duration_ms)

        # Average durations per date
        avg_duration_by_date = {
            d: sum(v) // len(v) for d, v in duration_by_date.items()
        }

        # Average agent durations
        avg_agent_durations = {
            name: sum(vals) // len(vals) for name, vals in agent_durations.items()
        }

        return {
            "total": total,
            "avg_duration_ms": avg_dur,
            "avg_time_saved_min": round(avg_saved, 1),
            "total_time_saved_min": round(avg_saved * total, 1),
            "total_files": total_files,
            "total_additions": total_additions,
            "total_deletions": total_deletions,
            "risk_counts": risk_counts,
            "type_counts": type_counts,
            "priority_counts": priority_counts,
            "prs_by_date": dict(sorted(prs_by_date.items())),
            "avg_duration_by_date": dict(sorted(avg_duration_by_date.items())),
            "author_counts": author_counts,
            "avg_agent_durations": avg_agent_durations,
        }


# Global singleton
pr_store = PRStore()


@dataclass
class PipelineRecord:
    repo: str
    run_id: int
    workflow: str
    branch: str
    commit_sha: str
    status: str
    failed_jobs: list = field(default_factory=list)
    analysis: str = ""
    run_url: str = ""
    autoheal_status: str = ""  # fix_applied, fix_failed, not_fixable, ""
    autoheal_pr: str = ""
    timestamp: float = field(default_factory=time.time)


class PipelineStore:
    """Thread-safe in-memory store for pipeline failure records."""

    MAX_RECORDS = 500

    def __init__(self):
        self._records: list[PipelineRecord] = []
        self._lock = threading.Lock()

    def add(self, record: PipelineRecord):
        with self._lock:
            self._records.insert(0, record)
            if len(self._records) > self.MAX_RECORDS:
                self._records = self._records[:self.MAX_RECORDS]

    def all(self) -> list[PipelineRecord]:
        with self._lock:
            return list(self._records)

    def get(self, repo: str, run_id: int) -> Optional[PipelineRecord]:
        with self._lock:
            for r in self._records:
                if r.repo == repo and r.run_id == run_id:
                    return r
            return None

    def stats(self) -> dict:
        with self._lock:
            total = len(self._records)
            if total == 0:
                return {"total": 0, "repos": {}}
            repos = {}
            for r in self._records:
                repos[r.repo] = repos.get(r.repo, 0) + 1
            return {"total": total, "repos": repos}


pipeline_store = PipelineStore()
