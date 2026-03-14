"""
SLA tracking — define targets per API and track compliance over time.
"""
import structlog
from app.services.cloudwatch import CloudWatchService
from app.services.cache import CacheService
from app.services.dynamodb import DynamoDBService
from app.config import get_settings

logger = structlog.get_logger()

# Default SLA targets (can be overridden per API via config endpoint)
DEFAULT_SLA = {
    "max_error_rate_pct": 1.0,
    "max_p99_latency_ms": 3000,
    "min_uptime_pct": 99.9,
}


class SLATracker:
    def __init__(self):
        self.cw = CloudWatchService()
        self.cache = CacheService()
        self.db = DynamoDBService()
        self.settings = get_settings()

    def get_sla_targets(self, api_path: str) -> dict:
        """Get SLA targets for an API (from cache or defaults)."""
        cached = self.cache.get(f"sla:targets:{api_path}")
        if cached:
            return cached
        return DEFAULT_SLA.copy()

    def set_sla_targets(self, api_path: str, targets: dict) -> dict:
        """Set custom SLA targets for an API."""
        sla = DEFAULT_SLA.copy()
        sla.update(targets)
        self.cache.set(f"sla:targets:{api_path}", sla, ttl_seconds=86400)
        self.db.store_audit_log({
            "action": "sla_target_update",
            "api_path": api_path,
            "targets": sla,
        })
        return sla

    def check_sla_compliance(self, api_path: str, hours_back: int = 24) -> dict:
        """Check if an API is meeting its SLA targets."""
        targets = self.get_sla_targets(api_path)
        metrics = self.cw.get_api_metrics(api_path, period_minutes=hours_back * 60)
        latency = self.cw.get_latency_metrics(api_path, period_minutes=hours_back * 60)

        error_rate = metrics.get("error_rate", 0)
        p99 = latency.get("p99_latency_ms", 0)
        total = metrics.get("total_requests", 0)
        errors = metrics.get("error_count", 0)
        uptime_pct = ((total - errors) / total * 100) if total > 0 else 100.0

        violations = []
        if error_rate > targets["max_error_rate_pct"]:
            violations.append({
                "metric": "error_rate",
                "target": targets["max_error_rate_pct"],
                "actual": round(error_rate, 2),
                "severity": "critical" if error_rate > targets["max_error_rate_pct"] * 5 else "warning",
            })
        if p99 > targets["max_p99_latency_ms"]:
            violations.append({
                "metric": "p99_latency_ms",
                "target": targets["max_p99_latency_ms"],
                "actual": round(p99, 1),
                "severity": "critical" if p99 > targets["max_p99_latency_ms"] * 2 else "warning",
            })
        if uptime_pct < targets["min_uptime_pct"]:
            violations.append({
                "metric": "uptime_pct",
                "target": targets["min_uptime_pct"],
                "actual": round(uptime_pct, 3),
                "severity": "critical" if uptime_pct < 99.0 else "warning",
            })

        compliant = len(violations) == 0

        result = {
            "api_path": api_path,
            "period_hours": hours_back,
            "compliant": compliant,
            "targets": targets,
            "actuals": {
                "error_rate_pct": round(error_rate, 2),
                "p99_latency_ms": round(p99, 1),
                "uptime_pct": round(uptime_pct, 3),
                "total_requests": total,
            },
            "violations": violations,
        }

        # Store SLA check result
        self.db.store_audit_log({
            "action": "sla_check",
            "api_path": api_path,
            "compliant": compliant,
            "violations_count": len(violations),
        })

        return result
