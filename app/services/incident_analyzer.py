"""Incident timeline, period comparison, and recurring error detection."""
import hashlib
import structlog
from datetime import datetime
from app.services.cloudwatch import (
    CloudWatchService, F_PATH, F_METHOD, F_STATUS, F_DURATION,
    F_MESSAGE, F_ERROR_CODE, F_LEVEL
)
from app.services.cache import CacheService
from app.config import get_settings

logger = structlog.get_logger()


class IncidentAnalyzer:
    def __init__(self):
        self.cw = CloudWatchService()
        self.cache = CacheService()
        self.settings = get_settings()

    def build_incident_timeline(self, start_hour: int, end_hour: int, date: str = None) -> dict:
        base = datetime.fromisoformat(date) if date else datetime.utcnow()
        start_time = base.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        end_time = base.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        hours_back = max(1, int((datetime.utcnow() - start_time).total_seconds() / 3600))
        api_filter = self.cw._api_filter

        errors = self.cw.query_logs(f"""fields @timestamp, {F_PATH}, {F_METHOD}, {F_STATUS}, {F_MESSAGE}, {F_ERROR_CODE}
| filter ({F_LEVEL} = "error" or {F_STATUS} >= 400) and {api_filter}
| filter @timestamp >= "{start_time.isoformat()}" and @timestamp <= "{end_time.isoformat()}"
| sort @timestamp asc | limit 200""", hours_back)

        slow = self.cw.query_logs(f"""fields @timestamp, {F_PATH}, {F_METHOD}, {F_DURATION}
| filter {F_MESSAGE} = "Request completed" and ispresent({F_DURATION}) and {api_filter}
| parse {F_DURATION} /(?<d>\\d+)/ | filter d > {self.settings.slow_api_threshold_ms}
| filter @timestamp >= "{start_time.isoformat()}" and @timestamp <= "{end_time.isoformat()}"
| sort @timestamp asc | limit 100""", hours_back)

        events = [{"timestamp": e.get("@timestamp", ""), "type": "error", "api_path": e.get(F_PATH, ""),
                    "status_code": e.get(F_STATUS, ""), "message": e.get(F_MESSAGE, "")[:200]} for e in errors]
        events += [{"timestamp": s.get("@timestamp", ""), "type": "slow_request",
                     "api_path": s.get(F_PATH, ""), "duration": s.get(F_DURATION, "")} for s in slow]
        events.sort(key=lambda e: e.get("timestamp", ""))

        return {"time_window": {"start": start_time.isoformat(), "end": end_time.isoformat()},
                "total_events": len(events), "error_count": len(errors),
                "slow_request_count": len(slow), "timeline": events}

    def compare_periods(self, api_path: str, p1_hours: int = 24, p2_hours: int = 48) -> dict:
        """Compare current period vs previous period of equal length."""
        # Current period: last p1_hours
        m1 = self.cw.get_api_metrics(api_path, period_minutes=p1_hours * 60)
        l1 = self.cw.get_latency_metrics(api_path, period_minutes=p1_hours * 60)
        # Previous period: p1_hours before that (total lookback = p2_hours)
        m2 = self.cw.get_api_metrics(api_path, period_minutes=p2_hours * 60)
        l2 = self.cw.get_latency_metrics(api_path, period_minutes=p2_hours * 60)

        # Approximate the previous-only period by subtracting current from total
        prev_total = max(0, m2["total_requests"] - m1["total_requests"])
        prev_errors = max(0, m2.get("error_count", 0) - m1.get("error_count", 0))
        prev_error_rate = (prev_errors / prev_total * 100) if prev_total else 0.0
        prev_avg_latency = l2["avg_latency_ms"]  # approximation

        def pct(new, old):
            return round(((new - old) / old) * 100, 1) if old else 0

        return {"api_path": api_path, "period1": f"last {p1_hours}h", "period2": f"previous {p2_hours - p1_hours}h",
                "comparison": {
                    "error_rate": {"current": m1["error_rate"], "previous": round(prev_error_rate, 2),
                                   "change_pct": pct(m1["error_rate"], prev_error_rate)},
                    "avg_latency_ms": {"current": l1["avg_latency_ms"], "previous": prev_avg_latency,
                                       "change_pct": pct(l1["avg_latency_ms"], prev_avg_latency)},
                    "total_requests": {"current": m1["total_requests"], "previous": prev_total,
                                       "change_pct": pct(m1["total_requests"], prev_total)},
                }}

    def detect_recurring_errors(self, hours_back: int = 168) -> list[dict]:
        api_filter = self.cw._api_filter
        logs = self.cw.query_logs(f"""fields @timestamp, {F_PATH}, {F_STATUS}, {F_MESSAGE}, {F_ERROR_CODE}
| filter ({F_STATUS} >= 500 or {F_LEVEL} = "error") and {api_filter} | sort @timestamp desc | limit 500""", hours_back)

        groups: dict[str, dict] = {}
        for entry in logs:
            msg = entry.get(F_MESSAGE, "")
            fp = hashlib.md5(msg.strip().lower().encode()).hexdigest()[:12]
            ts = entry.get("@timestamp", "")
            day = ts[:10]
            if fp not in groups:
                groups[fp] = {"fingerprint": fp, "api_path": entry.get(F_PATH, ""),
                              "status_code": entry.get(F_STATUS, ""), "error_code": entry.get(F_ERROR_CODE, ""),
                              "sample_message": msg[:300], "total_occurrences": 0,
                              "days_seen": set(), "first_seen": ts, "last_seen": ts}
            groups[fp]["total_occurrences"] += 1
            groups[fp]["last_seen"] = ts
            if day:
                groups[fp]["days_seen"].add(day)

        recurring = []
        for g in groups.values():
            days = g.pop("days_seen")
            g["unique_days"] = len(days)
            if g["unique_days"] >= 2:
                g["recurring"] = True
                recurring.append(g)
        recurring.sort(key=lambda x: x["total_occurrences"], reverse=True)
        return recurring
