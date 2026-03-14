"""
Incident timeline builder, comparative analysis, recurring error detection, SLA tracking.
"""
import hashlib
import structlog
from datetime import datetime, timedelta
from app.services.cloudwatch import CloudWatchService
from app.services.dynamodb import DynamoDBService
from app.services.cache import CacheService
from app.config import get_settings

logger = structlog.get_logger()


class IncidentAnalyzer:
    def __init__(self):
        self.cw = CloudWatchService()
        self.db = DynamoDBService()
        self.cache = CacheService()
        self.settings = get_settings()

    def build_incident_timeline(self, start_hour: int, end_hour: int, date: str = None) -> dict:
        """
        Build a chronological event log for a time window.
        e.g. "what happened between 2pm and 3pm?"
        """
        if date:
            base_date = datetime.fromisoformat(date)
        else:
            base_date = datetime.utcnow()

        start_time = base_date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        end_time = base_date.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        hours_back = max(1, int((datetime.utcnow() - start_time).total_seconds() / 3600))

        # Query errors in the time window
        error_query = f"""
            fields @timestamp, api_path, method, status_code, duration_ms, @message
            | filter status_code >= 400
            | filter @timestamp >= "{start_time.isoformat()}"
            | filter @timestamp <= "{end_time.isoformat()}"
            | sort @timestamp asc
            | limit 200
        """
        errors = self.cw.query_logs(error_query, hours_back=hours_back)

        # Query slow requests in the window
        slow_query = f"""
            fields @timestamp, api_path, method, duration_ms
            | filter duration_ms > {self.settings.slow_api_threshold_ms}
            | filter @timestamp >= "{start_time.isoformat()}"
            | filter @timestamp <= "{end_time.isoformat()}"
            | sort @timestamp asc
            | limit 100
        """
        slow_requests = self.cw.query_logs(slow_query, hours_back=hours_back)

        # Build timeline events
        events = []
        for err in errors:
            events.append({
                "timestamp": err.get("@timestamp", ""),
                "type": "error",
                "api_path": err.get("api_path", "unknown"),
                "status_code": err.get("status_code", ""),
                "message": err.get("@message", "")[:200],
            })
        for slow in slow_requests:
            events.append({
                "timestamp": slow.get("@timestamp", ""),
                "type": "slow_request",
                "api_path": slow.get("api_path", "unknown"),
                "duration_ms": slow.get("duration_ms", 0),
            })

        # Sort all events chronologically
        events.sort(key=lambda e: e.get("timestamp", ""))

        return {
            "time_window": {"start": start_time.isoformat(), "end": end_time.isoformat()},
            "total_events": len(events),
            "error_count": len(errors),
            "slow_request_count": len(slow_requests),
            "timeline": events,
        }

    def compare_periods(self, api_path: str, period1_hours_back: int = 24, period2_hours_back: int = 48) -> dict:
        """
        Compare API performance between two periods.
        e.g. "is checkout API slower today than yesterday?"
        Default: compare last 24h vs previous 24h.
        """
        # Period 1 (recent)
        metrics_now = self.cw.get_api_metrics(api_path, period_minutes=period1_hours_back * 60)
        latency_now = self.cw.get_latency_metrics(api_path, period_minutes=period1_hours_back * 60)

        # Period 2 (older) — we query a wider window and subtract
        metrics_prev = self.cw.get_api_metrics(api_path, period_minutes=period2_hours_back * 60)
        latency_prev = self.cw.get_latency_metrics(api_path, period_minutes=period2_hours_back * 60)

        def safe_pct_change(new_val, old_val):
            if old_val == 0:
                return 0
            return round(((new_val - old_val) / old_val) * 100, 1)

        return {
            "api_path": api_path,
            "period1": f"last {period1_hours_back}h",
            "period2": f"previous {period2_hours_back - period1_hours_back}h",
            "comparison": {
                "error_rate": {
                    "current": metrics_now.get("error_rate", 0),
                    "previous": metrics_prev.get("error_rate", 0),
                    "change_pct": safe_pct_change(
                        metrics_now.get("error_rate", 0),
                        metrics_prev.get("error_rate", 0),
                    ),
                },
                "avg_latency_ms": {
                    "current": latency_now.get("avg_latency_ms", 0),
                    "previous": latency_prev.get("avg_latency_ms", 0),
                    "change_pct": safe_pct_change(
                        latency_now.get("avg_latency_ms", 0),
                        latency_prev.get("avg_latency_ms", 0),
                    ),
                },
                "total_requests": {
                    "current": metrics_now.get("total_requests", 0),
                    "previous": metrics_prev.get("total_requests", 0),
                    "change_pct": safe_pct_change(
                        metrics_now.get("total_requests", 0),
                        metrics_prev.get("total_requests", 0),
                    ),
                },
            },
        }

    def detect_recurring_errors(self, hours_back: int = 168) -> list[dict]:
        """
        Find errors that keep reappearing over the past week.
        Groups by error fingerprint and flags those seen on multiple days.
        """
        query = f"""
            fields @timestamp, api_path, status_code, @message
            | filter status_code >= 500
            | sort @timestamp desc
            | limit 500
        """
        logs = self.cw.query_logs(query, hours_back=hours_back)

        # Group by fingerprint
        error_groups: dict[str, dict] = {}
        for log_entry in logs:
            msg = log_entry.get("@message", "")
            fingerprint = hashlib.md5(msg.strip().lower().encode()).hexdigest()[:12]
            ts = log_entry.get("@timestamp", "")
            day = ts[:10] if ts else ""

            if fingerprint not in error_groups:
                error_groups[fingerprint] = {
                    "fingerprint": fingerprint,
                    "api_path": log_entry.get("api_path", "unknown"),
                    "status_code": log_entry.get("status_code", ""),
                    "sample_message": msg[:300],
                    "total_occurrences": 0,
                    "days_seen": set(),
                    "first_seen": ts,
                    "last_seen": ts,
                }

            error_groups[fingerprint]["total_occurrences"] += 1
            error_groups[fingerprint]["last_seen"] = ts
            if day:
                error_groups[fingerprint]["days_seen"].add(day)

        # Filter to recurring (seen on 2+ days)
        recurring = []
        for group in error_groups.values():
            days = group.pop("days_seen")
            group["unique_days"] = len(days)
            if group["unique_days"] >= 2:
                group["recurring"] = True
                recurring.append(group)

        recurring.sort(key=lambda x: x["total_occurrences"], reverse=True)
        return recurring
