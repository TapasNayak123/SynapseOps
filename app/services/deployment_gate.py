"""Deployment Gate — AI-driven deploy/hold decision based on live traffic analysis.

Analyzes current traffic volume, error rates, and latency to determine if it's
safe to deploy. If traffic is at peak or the system is unhealthy, the deployment
is held and the team is notified. A background job rechecks held deployments
and releases them when conditions improve.

Held deployments are persisted to DynamoDB so the gate survives restarts.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from app.config import get_settings
from app.services.cloudwatch import CloudWatchService
from app.services.cache import CacheService
from app.services.notifier import NotifierService, _get_http, _WEBHOOK_RETRYABLE
from app.services.retry import retry_with_backoff
from activity_log import activity_log

logger = logging.getLogger(__name__)

# ── Thresholds for deployment safety ──────────────────────────────────────

PEAK_TRAFFIC_MULTIPLIER = 1.5
MAX_ERROR_RATE_FOR_DEPLOY = 5.0
MAX_P99_LATENCY_FOR_DEPLOY = 3000
RECHECK_INTERVAL = 120
MAX_HOLD_DURATION = 3600

# ── DynamoDB helpers ──────────────────────────────────────────────────────

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


def _ensure_table(table_name: str):
    """Create the held-deployments table if it doesn't exist."""
    resource = _get_resource()
    try:
        table = resource.Table(table_name)
        table.table_status
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
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    logger.info("Table %s created", table_name)
    return table


def _float_to_decimal(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _float_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_float_to_decimal(i) for i in obj]
    return obj


def _decimal_to_float(obj):
    if isinstance(obj, Decimal):
        if obj == int(obj):
            return int(obj)
        return float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_float(i) for i in obj]
    return obj


# ── Data model ────────────────────────────────────────────────────────────

@dataclass
class HeldDeployment:
    """A deployment that's been held pending better conditions."""
    repo: str
    run_id: int
    workflow: str
    branch: str
    commit_sha: str
    sender: str
    hold_reason: str
    traffic_snapshot: dict
    held_at: float = field(default_factory=time.time)
    released: bool = False
    release_reason: str = ""


class DeploymentGate:
    """Evaluates whether it's safe to deploy based on live traffic analysis.

    Held deployments are persisted to a DynamoDB table so they survive
    application restarts. The table key is ``pk=repo, sk=run_id``.
    """

    def __init__(self):
        self.cw = CloudWatchService()
        self.cache = CacheService()
        self.notifier = NotifierService()
        self.settings = get_settings()
        self._lock = threading.Lock()

        # DynamoDB table for held deployments
        prefix = self.settings.dynamodb_table_prefix
        self._table_name = f"{prefix}-held-deployments"
        self._table = None
        self._table_lock = threading.Lock()

    # ── DynamoDB access ───────────────────────────────────────────────

    def _get_table(self):
        if self._table is None:
            with self._table_lock:
                if self._table is None:
                    self._table = _ensure_table(self._table_name)
        return self._table

    def _to_item(self, held: HeldDeployment) -> dict:
        item = {
            "pk": held.repo,
            "sk": str(held.run_id),
            "repo": held.repo,
            "run_id": held.run_id,
            "workflow": held.workflow,
            "branch": held.branch,
            "commit_sha": held.commit_sha,
            "sender": held.sender,
            "hold_reason": held.hold_reason,
            "traffic_snapshot": held.traffic_snapshot,
            "held_at": held.held_at,
            "released": held.released,
            "release_reason": held.release_reason,
        }
        return _float_to_decimal(item)

    def _from_item(self, item: dict) -> HeldDeployment:
        item = _decimal_to_float(item)
        return HeldDeployment(
            repo=item["repo"],
            run_id=int(item["run_id"]),
            workflow=item.get("workflow", ""),
            branch=item.get("branch", ""),
            commit_sha=item.get("commit_sha", ""),
            sender=item.get("sender", ""),
            hold_reason=item.get("hold_reason", ""),
            traffic_snapshot=item.get("traffic_snapshot", {}),
            held_at=float(item.get("held_at", 0)),
            released=bool(item.get("released", False)),
            release_reason=item.get("release_reason", ""),
        )

    def _save_held(self, held: HeldDeployment):
        """Persist a held deployment to DynamoDB."""
        try:
            self._get_table().put_item(Item=self._to_item(held))
        except Exception:
            logger.exception("Failed to persist held deployment %s run %s", held.repo, held.run_id)

    def _load_pending(self) -> list[HeldDeployment]:
        """Load all non-released held deployments from DynamoDB."""
        try:
            items = self._get_table().scan(
                FilterExpression="released = :f",
                ExpressionAttributeValues={":f": False},
            ).get("Items", [])
            return [self._from_item(i) for i in items]
        except Exception:
            logger.exception("Failed to load held deployments from DynamoDB")
            return []

    def _load_all(self) -> list[HeldDeployment]:
        """Load all held deployments (including released) from DynamoDB."""
        try:
            items = self._get_table().scan().get("Items", [])
            return [self._from_item(i) for i in items]
        except Exception:
            logger.exception("Failed to load held deployments from DynamoDB")
            return []

    def evaluate(self, repo: str, run_id: int, workflow: str,
                 branch: str, commit_sha: str, sender: str) -> dict:
        """Analyze current conditions and decide: deploy or hold.

        Returns dict with:
            - decision: "deploy" | "hold"
            - reason: human-readable explanation
            - analysis: detailed traffic/health snapshot
        """
        activity_log.emit(
            "Deployment Gate", "started",
            f"Evaluating deployment safety for {repo} ({workflow})",
            repo=repo,
        )

        analysis = self._analyze_current_conditions()

        reasons = []

        # Check 1: Peak traffic
        if analysis["is_peak_traffic"]:
            reasons.append(
                f"Traffic is at peak ({analysis['current_requests']} reqs in last 5min, "
                f"baseline avg is {analysis['baseline_avg_requests']})"
            )

        # Check 2: High error rate
        if analysis["error_rate"] > MAX_ERROR_RATE_FOR_DEPLOY:
            reasons.append(
                f"Error rate is elevated at {analysis['error_rate']:.1f}% "
                f"(threshold: {MAX_ERROR_RATE_FOR_DEPLOY}%)"
            )

        # Check 3: High latency
        if analysis["p99_latency_ms"] > MAX_P99_LATENCY_FOR_DEPLOY:
            reasons.append(
                f"P99 latency is {analysis['p99_latency_ms']:.0f}ms "
                f"(threshold: {MAX_P99_LATENCY_FOR_DEPLOY}ms)"
            )

        if reasons:
            hold_reason = "; ".join(reasons)
            held = HeldDeployment(
                repo=repo, run_id=run_id, workflow=workflow,
                branch=branch, commit_sha=commit_sha, sender=sender,
                hold_reason=hold_reason, traffic_snapshot=analysis,
            )
            self._save_held(held)

            activity_log.emit(
                "Deployment Gate", "completed",
                f"HOLD — {hold_reason}",
                repo=repo,
            )
            self._notify_hold(held)

            return {
                "decision": "hold",
                "reason": hold_reason,
                "analysis": analysis,
                "message": "Deployment held. Will auto-release when conditions improve.",
            }

        activity_log.emit(
            "Deployment Gate", "completed",
            "DEPLOY — all conditions safe",
            repo=repo,
        )
        self._notify_deploy(repo, workflow, branch, commit_sha, sender, analysis)

        return {
            "decision": "deploy",
            "reason": "Traffic is normal, error rate and latency are within safe limits.",
            "analysis": analysis,
        }

    def _analyze_current_conditions(self) -> dict:
        """Gather traffic, error rate, and latency across all monitored APIs."""
        apis = self._get_monitored_apis()

        total_current = 0
        total_errors = 0
        total_requests_baseline = 0
        max_p99 = 0.0
        api_details = []

        for api in apis:
            # Current 5-minute window
            current = self.cw.get_api_metrics(api, period_minutes=5)
            latency = self.cw.get_latency_metrics(api, period_minutes=5)

            # Baseline: average over the last 60 minutes (12 x 5-min windows)
            baseline = self.cw.get_api_metrics(api, period_minutes=60)

            current_reqs = current.get("total_requests", 0)
            baseline_reqs = baseline.get("total_requests", 0)
            # Normalize baseline to 5-min equivalent
            baseline_5min = baseline_reqs / 12 if baseline_reqs else 0

            total_current += current_reqs
            total_errors += current.get("error_count", 0)
            total_requests_baseline += baseline_5min
            max_p99 = max(max_p99, latency.get("p99_latency_ms", 0))

            api_details.append({
                "api": api,
                "current_5min_requests": current_reqs,
                "baseline_5min_avg": round(baseline_5min, 1),
                "error_rate": current.get("error_rate", 0),
                "p99_latency_ms": latency.get("p99_latency_ms", 0),
            })

        overall_error_rate = (total_errors / total_current * 100) if total_current else 0.0
        is_peak = (
            total_current > total_requests_baseline * PEAK_TRAFFIC_MULTIPLIER
            and total_current > 10  # avoid false positives on very low traffic
        )

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "current_requests": total_current,
            "baseline_avg_requests": round(total_requests_baseline, 1),
            "traffic_ratio": round(total_current / total_requests_baseline, 2) if total_requests_baseline else 0,
            "is_peak_traffic": is_peak,
            "error_rate": round(overall_error_rate, 2),
            "p99_latency_ms": round(max_p99, 1),
            "monitored_apis": len(apis),
            "api_details": api_details,
        }

    def recheck_held_deployments(self):
        """Called periodically by the scheduler. Re-evaluates held deployments."""
        pending = self._load_pending()

        if not pending:
            return

        analysis = self._analyze_current_conditions()
        now = time.time()

        for held in pending:
            elapsed = now - held.held_at
            force_release = elapsed > MAX_HOLD_DURATION

            safe = (
                not analysis["is_peak_traffic"]
                and analysis["error_rate"] <= MAX_ERROR_RATE_FOR_DEPLOY
                and analysis["p99_latency_ms"] <= MAX_P99_LATENCY_FOR_DEPLOY
            )

            if safe or force_release:
                held.released = True
                if force_release and not safe:
                    held.release_reason = (
                        f"Max hold duration ({MAX_HOLD_DURATION // 60}min) exceeded. "
                        f"Releasing despite conditions: traffic_ratio={analysis['traffic_ratio']}, "
                        f"error_rate={analysis['error_rate']}%"
                    )
                else:
                    held.release_reason = (
                        f"Conditions improved: traffic_ratio={analysis['traffic_ratio']}, "
                        f"error_rate={analysis['error_rate']}%, "
                        f"p99={analysis['p99_latency_ms']}ms"
                    )

                self._save_held(held)

                logger.info(
                    "Releasing held deployment: %s run %s — %s",
                    held.repo, held.run_id, held.release_reason,
                )
                activity_log.emit(
                    "Deployment Gate", "completed",
                    f"RELEASED — {held.release_reason}",
                    repo=held.repo,
                )
                self._notify_release(held, analysis)

    def get_held_deployments(self) -> list[dict]:
        """Return all held deployments (including released) from DynamoDB."""
        deployments = self._load_all()
        return [
            {
                "repo": h.repo, "run_id": h.run_id, "workflow": h.workflow,
                "branch": h.branch, "commit_sha": h.commit_sha, "sender": h.sender,
                "hold_reason": h.hold_reason, "held_at": h.held_at,
                "released": h.released, "release_reason": h.release_reason,
                "held_for_seconds": int(time.time() - h.held_at),
            }
            for h in deployments
        ]

    def _get_monitored_apis(self) -> list[str]:
        apis = self.cache.get("monitored_apis")
        if apis:
            return apis
        if self.settings.monitored_apis:
            return [a.strip() for a in self.settings.monitored_apis.split(",") if a.strip()]
        return []

    # ── Teams Notifications ───────────────────────────────────────────

    def _notify_hold(self, held: HeldDeployment):
        webhook_url = self.settings.teams_webhook_url
        if not webhook_url:
            return

        payload = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "Container",
                            "style": "attention",
                            "items": [{
                                "type": "TextBlock",
                                "text": "⏸️ Deployment Held",
                                "size": "large",
                                "weight": "bolder",
                                "color": "attention",
                            }],
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "📦 Repo", "value": held.repo},
                                {"title": "⚙️ Workflow", "value": held.workflow},
                                {"title": "🔀 Branch", "value": held.branch},
                                {"title": "📝 Commit", "value": held.commit_sha},
                                {"title": "👤 Triggered by", "value": held.sender},
                            ],
                        },
                        {
                            "type": "TextBlock",
                            "text": f"**Reason:** {held.hold_reason}",
                            "wrap": True,
                            "spacing": "medium",
                            "separator": True,
                        },
                        {
                            "type": "TextBlock",
                            "text": (
                                f"📊 Current traffic: **{held.traffic_snapshot['current_requests']}** reqs/5min "
                                f"(baseline: {held.traffic_snapshot['baseline_avg_requests']})\n\n"
                                f"📈 Traffic ratio: **{held.traffic_snapshot['traffic_ratio']}x**\n\n"
                                f"❌ Error rate: **{held.traffic_snapshot['error_rate']}%**\n\n"
                                f"⏱️ P99 latency: **{held.traffic_snapshot['p99_latency_ms']}ms**"
                            ),
                            "wrap": True,
                            "size": "small",
                        },
                        {
                            "type": "TextBlock",
                            "text": "The deployment will be automatically released when conditions improve.",
                            "wrap": True,
                            "size": "small",
                            "isSubtle": True,
                            "spacing": "medium",
                        },
                    ],
                },
            }],
        }

        try:
            _send_gate_notification(webhook_url, payload)
        except Exception:
            logger.exception("Failed to send deployment hold notification")

    def _notify_deploy(self, repo: str, workflow: str, branch: str,
                       commit_sha: str, sender: str, analysis: dict):
        webhook_url = self.settings.teams_webhook_url
        if not webhook_url:
            return

        payload = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "Container",
                            "style": "good",
                            "items": [{
                                "type": "TextBlock",
                                "text": "✅ Deployment Approved",
                                "size": "large",
                                "weight": "bolder",
                                "color": "good",
                            }],
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "📦 Repo", "value": repo},
                                {"title": "⚙️ Workflow", "value": workflow},
                                {"title": "🔀 Branch", "value": branch},
                                {"title": "📝 Commit", "value": commit_sha},
                                {"title": "👤 Triggered by", "value": sender},
                                {"title": "📊 Traffic ratio", "value": f"{analysis['traffic_ratio']}x"},
                                {"title": "❌ Error rate", "value": f"{analysis['error_rate']}%"},
                                {"title": "⏱️ P99 latency", "value": f"{analysis['p99_latency_ms']}ms"},
                            ],
                        },
                        {
                            "type": "TextBlock",
                            "text": "All conditions are within safe limits. Deployment can proceed.",
                            "wrap": True,
                            "size": "small",
                            "isSubtle": True,
                        },
                    ],
                },
            }],
        }

        try:
            _send_gate_notification(webhook_url, payload)
        except Exception:
            logger.exception("Failed to send deployment approved notification")

    def _notify_release(self, held: HeldDeployment, analysis: dict):
        webhook_url = self.settings.teams_webhook_url
        if not webhook_url:
            return

        held_minutes = int((time.time() - held.held_at) / 60)

        payload = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "Container",
                            "style": "good",
                            "items": [{
                                "type": "TextBlock",
                                "text": "▶️ Held Deployment Released",
                                "size": "large",
                                "weight": "bolder",
                                "color": "good",
                            }],
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "📦 Repo", "value": held.repo},
                                {"title": "⚙️ Workflow", "value": held.workflow},
                                {"title": "🔀 Branch", "value": held.branch},
                                {"title": "📝 Commit", "value": held.commit_sha},
                                {"title": "⏳ Held for", "value": f"{held_minutes} minutes"},
                                {"title": "📊 Traffic ratio now", "value": f"{analysis['traffic_ratio']}x"},
                                {"title": "❌ Error rate now", "value": f"{analysis['error_rate']}%"},
                                {"title": "⏱️ P99 latency now", "value": f"{analysis['p99_latency_ms']}ms"},
                            ],
                        },
                        {
                            "type": "TextBlock",
                            "text": f"**Release reason:** {held.release_reason}",
                            "wrap": True,
                            "spacing": "medium",
                            "separator": True,
                        },
                        {
                            "type": "TextBlock",
                            "text": "Deployment can now proceed safely.",
                            "wrap": True,
                            "size": "small",
                            "isSubtle": True,
                        },
                    ],
                },
            }],
        }

        try:
            _send_gate_notification(webhook_url, payload)
        except Exception:
            logger.exception("Failed to send deployment release notification")


@retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=15.0, retryable_exceptions=_WEBHOOK_RETRYABLE)
def _send_gate_notification(webhook_url: str, payload: dict):
    resp = _get_http().post(webhook_url, json=payload, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    logger.info("Deployment gate notification sent")


# ── Singleton ─────────────────────────────────────────────────────────────

_gate: Optional[DeploymentGate] = None
_gate_lock = threading.Lock()


def get_deployment_gate() -> DeploymentGate:
    global _gate
    if _gate is None:
        with _gate_lock:
            if _gate is None:
                _gate = DeploymentGate()
    return _gate
