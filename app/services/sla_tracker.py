"""SLA compliance tracking with configurable per-API targets."""
import structlog
from app.services.cloudwatch import CloudWatchService
from app.services.cache import CacheService
from app.services.dynamodb import DynamoDBService

logger = structlog.get_logger()

DEFAULT_SLA = {"max_error_rate_pct": 1.0, "max_p99_latency_ms": 3000, "min_uptime_pct": 99.9}


class SLATracker:
    def __init__(self):
        self.cw = CloudWatchService()
        self.cache = CacheService()
        self.db = DynamoDBService()

    def get_sla_targets(self, api_path: str) -> dict:
        return self.cache.get(f"sla:targets:{api_path}") or DEFAULT_SLA.copy()

    def set_sla_targets(self, api_path: str, targets: dict) -> dict:
        sla = DEFAULT_SLA.copy()
        sla.update(targets)
        self.cache.set(f"sla:targets:{api_path}", sla, ttl_seconds=86400)
        self.db.store_audit_log({"action": "sla_target_update", "api_path": api_path, "targets": sla})
        return sla

    def check_sla_compliance(self, api_path: str, hours_back: int = 24) -> dict:
        targets = self.get_sla_targets(api_path)
        period_minutes = min(hours_back * 60, 1440)  # Cap at 24h for performance
        metrics = self.cw.get_api_metrics(api_path, period_minutes=period_minutes)
        latency = self.cw.get_latency_metrics(api_path, period_minutes=period_minutes)

        er = metrics.get("error_rate", 0)
        p99 = latency.get("p99_latency_ms", 0)
        total = metrics.get("total_requests", 0)
        errors = metrics.get("error_count", 0)
        uptime = ((total - errors) / total * 100) if total else 100.0

        violations = []
        if er > targets["max_error_rate_pct"]:
            violations.append({"metric": "error_rate", "target": targets["max_error_rate_pct"],
                               "actual": round(er, 2), "severity": "critical" if er > targets["max_error_rate_pct"] * 5 else "warning"})
        if p99 > targets["max_p99_latency_ms"]:
            violations.append({"metric": "p99_latency_ms", "target": targets["max_p99_latency_ms"],
                               "actual": round(p99, 1), "severity": "critical" if p99 > targets["max_p99_latency_ms"] * 2 else "warning"})
        if uptime < targets["min_uptime_pct"]:
            violations.append({"metric": "uptime_pct", "target": targets["min_uptime_pct"],
                               "actual": round(uptime, 3), "severity": "critical" if uptime < 99.0 else "warning"})

        compliant = len(violations) == 0
        self.db.store_audit_log({"action": "sla_check", "api_path": api_path, "compliant": compliant})

        return {"api_path": api_path, "period_hours": hours_back, "compliant": compliant,
                "targets": targets, "actuals": {"error_rate_pct": round(er, 2), "p99_latency_ms": round(p99, 1),
                "uptime_pct": round(uptime, 3), "total_requests": total}, "violations": violations}
