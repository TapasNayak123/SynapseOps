"""Error rate monitoring with threshold alerting and cooldown."""
import structlog
from datetime import datetime, timedelta
from app.config import get_settings
from app.services.cloudwatch import CloudWatchService
from app.services.cache import CacheService
from app.services.dynamodb import DynamoDBService
from app.services.notifier import NotifierService
from app.models.schemas import HttpStatusCategory

logger = structlog.get_logger()


class ErrorAnalyzer:
    def __init__(self):
        self.cw = CloudWatchService()
        self.cache = CacheService()
        self.db = DynamoDBService()
        self.notifier = NotifierService()
        self.settings = get_settings()

    @staticmethod
    def categorize_status(status_code: int) -> HttpStatusCategory:
        if 200 <= status_code < 300:
            return HttpStatusCategory.SUCCESS_2XX
        if 300 <= status_code < 400:
            return HttpStatusCategory.REDIRECT_3XX
        if 400 <= status_code < 500:
            return HttpStatusCategory.CLIENT_ERROR_4XX
        return HttpStatusCategory.SERVER_ERROR_5XX

    def analyze_api_errors(self, api_path: str) -> dict:
        metrics = self.cw.get_api_metrics(api_path, period_minutes=1)
        # Use server_error_rate (5xx only) for threshold alerting
        error_rate = metrics["server_error_rate"]
        self.db.store_metric_snapshot(metrics)
        self.cache.set(f"metrics:latest:{api_path}", metrics, ttl_seconds=120)

        exceeded = error_rate >= self.settings.error_rate_threshold
        result = {"api_path": api_path, "error_rate": metrics["error_rate"],
                  "server_error_rate": error_rate,
                  "threshold": self.settings.error_rate_threshold, "exceeded": exceeded, "alerted": False}
        if exceeded:
            result["alerted"] = self._maybe_alert(api_path, metrics)
        return result

    def _maybe_alert(self, api_path: str, metrics: dict) -> bool:
        last = self.cache.get_last_alert_time(api_path)
        if last:
            cooldown = timedelta(minutes=self.settings.alert_cooldown_minutes)
            if datetime.utcnow() - datetime.fromisoformat(last) < cooldown:
                return False

        now = datetime.utcnow().isoformat()
        alert = {"api_path": api_path, "alert_type": "error_rate_exceeded",
                 "error_rate": metrics["error_rate"], "threshold": self.settings.error_rate_threshold,
                 "total_requests": metrics["total_requests"], "error_count": metrics["error_count"], "timestamp": now}
        self.notifier.send_teams_alert(alert)
        self.db.store_alert(alert)
        self.cache.set_last_alert_time(api_path, now)
        return True

    def get_errors_by_status(self, hours_back: int = 1) -> dict:
        """Single aggregated query for error breakdown by status code."""
        api_filter = self.cw._api_filter
        query = f"""fields @timestamp, statusCode, path, errorCode, message
            | filter statusCode >= 400 and {api_filter}
            | stats count(*) as cnt by statusCode
            | sort cnt desc"""
        results = self.cw.query_logs(query, hours_back, limit=50)

        categories = {}
        for row in results:
            sc = int(row.get("statusCode", 500))
            cat = self.categorize_status(sc).value
            categories.setdefault(cat, []).append({
                "status_code": sc, "count": int(row.get("cnt", 0)), "samples": []
            })
        return categories
