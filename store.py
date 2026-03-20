"""DynamoDB-backed store for PR and pipeline data. Survives restarts.

Keeps the same public interface (pr_store / pipeline_store singletons,
PRRecord / PipelineRecord / AgentResult dataclasses) so all existing
consumers work without changes.
"""

from __future__ import annotations

import datetime
import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from decimal import Decimal
from typing import Optional

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from app.config import get_settings

logger = logging.getLogger(__name__)

# ── Shared DynamoDB resource ──────────────────────────────────────────────

_resource = None
_resource_lock = threading.Lock()


def _get_resource():
    global _resource
    if _resource is None:
        with _resource_lock:
            if _resource is None:
                settings = get_settings()
                _resource = boto3.resource(
                    "dynamodb",
                    region_name=settings.aws_region,
                    config=BotoConfig(
                        retries={"max_attempts": 3, "mode": "adaptive"},
                        max_pool_connections=25,
                    ),
                )
    return _resource


def _ensure_table(table_name: str, pk_type: str = "S", sk_type: str = "S"):
    """Create a DynamoDB table if it doesn't exist."""
    resource = _get_resource()
    try:
        table = resource.Table(table_name)
        table.table_status  # triggers DescribeTable
        return table
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
    logger.info("Creating DynamoDB table: %s", table_name)
    table = resource.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": pk_type},
            {"AttributeName": "sk", "AttributeType": sk_type},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    logger.info("Table %s created", table_name)
    return table


def _float_to_decimal(obj):
    """Recursively convert floats to Decimal for DynamoDB.
    Handles NaN and Infinity which DynamoDB does not support."""
    if isinstance(obj, float):
        import math
        if math.isnan(obj) or math.isinf(obj):
            return Decimal("0")
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _float_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_float_to_decimal(i) for i in obj]
    return obj


def _decimal_to_float(obj):
    """Recursively convert Decimals back to float/int."""
    if isinstance(obj, Decimal):
        if obj == int(obj):
            return int(obj)
        return float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_float(i) for i in obj]
    return obj


def _paginated_scan(table, max_items: int = 1000) -> list[dict]:
    """Scan a DynamoDB table with pagination to handle large datasets."""
    items: list[dict] = []
    kwargs: dict = {}
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        if len(items) >= max_items:
            items = items[:max_items]
            break
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key
    return items


# ── Dataclasses (unchanged interface) ─────────────────────────────────────

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
    autoheal_status: str = ""
    autoheal_pr: str = ""
    timestamp: float = field(default_factory=time.time)


# ── PR Store (DynamoDB-backed) ────────────────────────────────────────────

class PRStore:
    """DynamoDB-backed store for PR records. Same interface as the old in-memory version."""

    def __init__(self):
        prefix = get_settings().dynamodb_table_prefix
        self._table_name = f"{prefix}-pr-records"
        self._table = None
        self._init_lock = threading.Lock()

    def _get_table(self):
        if self._table is None:
            with self._init_lock:
                if self._table is None:
                    self._table = _ensure_table(self._table_name)
        return self._table

    def _to_item(self, record: PRRecord) -> dict:
        """Convert PRRecord to a DynamoDB item."""
        item = {
            "pk": record.repo,
            "sk": f"{record.pr_number}#{record.timestamp}",
            "repo": record.repo,
            "pr_number": record.pr_number,
            "title": record.title,
            "author": record.author,
            "branch": record.branch,
            "target": record.target,
            "action": record.action,
            "summary": record.summary,
            "risk_level": record.risk_level,
            "pr_type": record.pr_type,
            "priority": record.priority,
            "agent_results": [asdict(ar) for ar in record.agent_results],
            "total_duration_ms": record.total_duration_ms,
            "files_changed": record.files_changed,
            "additions": record.additions,
            "deletions": record.deletions,
            "timestamp": record.timestamp,
        }
        return _float_to_decimal(item)

    def _from_item(self, item: dict) -> PRRecord:
        """Convert a DynamoDB item back to PRRecord."""
        item = _decimal_to_float(item)
        agent_results = [
            AgentResult(name=ar["name"], output=ar["output"], duration_ms=ar["duration_ms"])
            for ar in item.get("agent_results", [])
        ]
        return PRRecord(
            repo=item["repo"],
            pr_number=int(item["pr_number"]),
            title=item["title"],
            author=item["author"],
            branch=item["branch"],
            target=item["target"],
            action=item["action"],
            summary=item["summary"],
            risk_level=item["risk_level"],
            pr_type=item.get("pr_type", "Unknown"),
            priority=item.get("priority", "Medium"),
            agent_results=agent_results,
            total_duration_ms=int(item.get("total_duration_ms", 0)),
            files_changed=int(item.get("files_changed", 0)),
            additions=int(item.get("additions", 0)),
            deletions=int(item.get("deletions", 0)),
            timestamp=float(item.get("timestamp", 0)),
        )

    def add(self, record: PRRecord):
        try:
            self._get_table().put_item(Item=self._to_item(record))
        except Exception:
            logger.exception("Failed to store PR record %s #%s", record.repo, record.pr_number)

    def all(self) -> list[PRRecord]:
        try:
            items = _paginated_scan(self._get_table(), max_items=500)
            records = [self._from_item(i) for i in items]
            records.sort(key=lambda r: r.timestamp, reverse=True)
            return records
        except Exception:
            logger.exception("Failed to fetch PR records")
            return []

    def get(self, repo: str, pr_number: int) -> Optional[PRRecord]:
        try:
            resp = self._get_table().query(
                KeyConditionExpression="pk = :pk AND begins_with(sk, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": repo,
                    ":sk_prefix": f"{pr_number}#",
                },
                ScanIndexForward=False,
                Limit=1,
            )
            items = resp.get("Items", [])
            if items:
                return self._from_item(items[0])
            return None
        except Exception:
            logger.exception("Failed to get PR record %s #%s", repo, pr_number)
            return None

    def stats(self) -> dict:
        records = self.all()
        total = len(records)
        if total == 0:
            return {"total": 0, "avg_duration_ms": 0, "risk_counts": {}, "total_files": 0}

        avg_dur = sum(r.total_duration_ms for r in records) // total
        risk_counts = {}
        total_files = 0
        for r in records:
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
        records = self.all()
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
        avg_saved = max(0, 15 - (avg_dur / 60000))

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
            ptype = r.pr_type.split(" ", 1)[-1] if " " in r.pr_type else r.pr_type
            type_counts[ptype] = type_counts.get(ptype, 0) + 1
            pri = r.priority.split(" ", 1)[-1] if " " in r.priority else r.priority
            priority_counts[pri] = priority_counts.get(pri, 0) + 1

            day = datetime.datetime.fromtimestamp(r.timestamp).strftime("%Y-%m-%d")
            prs_by_date[day] = prs_by_date.get(day, 0) + 1
            duration_by_date.setdefault(day, []).append(r.total_duration_ms)

            author_counts[r.author] = author_counts.get(r.author, 0) + 1
            total_files += r.files_changed
            total_additions += r.additions
            total_deletions += r.deletions

            for ar in r.agent_results:
                agent_durations.setdefault(ar.name, []).append(ar.duration_ms)

        avg_duration_by_date = {d: sum(v) // len(v) for d, v in duration_by_date.items()}
        avg_agent_durations = {name: sum(vals) // len(vals) for name, vals in agent_durations.items()}

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


# ── Pipeline Store (DynamoDB-backed) ──────────────────────────────────────

class PipelineStore:
    """DynamoDB-backed store for pipeline failure records."""

    def __init__(self):
        prefix = get_settings().dynamodb_table_prefix
        self._table_name = f"{prefix}-pipeline-records"
        self._table = None
        self._init_lock = threading.Lock()

    def _get_table(self):
        if self._table is None:
            with self._init_lock:
                if self._table is None:
                    self._table = _ensure_table(self._table_name)
        return self._table

    def _to_item(self, record: PipelineRecord) -> dict:
        item = {
            "pk": record.repo,
            "sk": str(record.run_id),
            "repo": record.repo,
            "run_id": record.run_id,
            "workflow": record.workflow,
            "branch": record.branch,
            "commit_sha": record.commit_sha,
            "status": record.status,
            "failed_jobs": record.failed_jobs,
            "analysis": record.analysis,
            "run_url": record.run_url,
            "autoheal_status": record.autoheal_status,
            "autoheal_pr": record.autoheal_pr,
            "timestamp": record.timestamp,
        }
        return _float_to_decimal(item)

    def _from_item(self, item: dict) -> PipelineRecord:
        item = _decimal_to_float(item)
        return PipelineRecord(
            repo=item["repo"],
            run_id=int(item["run_id"]),
            workflow=item.get("workflow", "N/A"),
            branch=item.get("branch", "N/A"),
            commit_sha=item.get("commit_sha", ""),
            status=item.get("status", "failure"),
            failed_jobs=item.get("failed_jobs", []),
            analysis=item.get("analysis", ""),
            run_url=item.get("run_url", ""),
            autoheal_status=item.get("autoheal_status", ""),
            autoheal_pr=item.get("autoheal_pr", ""),
            timestamp=float(item.get("timestamp", 0)),
        )

    def add(self, record: PipelineRecord):
        try:
            self._get_table().put_item(Item=self._to_item(record))
        except Exception:
            logger.exception("Failed to store pipeline record %s run %s", record.repo, record.run_id)

    def all(self) -> list[PipelineRecord]:
        try:
            items = _paginated_scan(self._get_table(), max_items=500)
            records = [self._from_item(i) for i in items]
            records.sort(key=lambda r: r.timestamp, reverse=True)
            return records
        except Exception:
            logger.exception("Failed to fetch pipeline records")
            return []

    def get(self, repo: str, run_id: int) -> Optional[PipelineRecord]:
        try:
            resp = self._get_table().get_item(Key={"pk": repo, "sk": str(run_id)})
            item = resp.get("Item")
            if item:
                return self._from_item(item)
            return None
        except Exception:
            logger.exception("Failed to get pipeline record %s run %s", repo, run_id)
            return None

    def stats(self) -> dict:
        records = self.all()
        total = len(records)
        if total == 0:
            return {"total": 0, "repos": {}}
        repos = {}
        for r in records:
            repos[r.repo] = repos.get(r.repo, 0) + 1
        return {"total": total, "repos": repos}


# ── Global singletons ────────────────────────────────────────────────────

pr_store = PRStore()
pipeline_store = PipelineStore()
