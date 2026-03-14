import hashlib
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

    def categorize_status(self, status_code: int) -> HttpStatusCategory:
        if 200 <= status_code < 300:
            return HttpStatusCategory.SUCCESS_2XX
        elif 300 <= status_code < 400:
            return HttpStatusCategory.REDIRECT_3XX
        elif 400 <= status_code < 500:
            return HttpStatusCategory.CLIENT_ERROR_4XX
        else:
            return HttpStatusCategory.SERVER_ERROR_5XX

    def fingerprint_error(self, error_message: str) -> str:
        """Create a hash fingerprint for error grouping."""
        normalized = error_message.strip().lower()
        return hashlib.md5(normalized.encode()).hexdigest()[:12]

    def analyze_api_errors(self, api_path: str) -> dict:
        """Analyze error rate for an API and trigger alert if threshold exceeded."""
        metrics = self.cw.get_api_metrics(api_path, period_minutes=1)
        error_rate = metrics["error_rate"]

        # Store metric snapshot
        self.db.store_metric_snapshot(metrics)
        self.cache.set(f"metrics:latest:{api_path}", metrics, ttl_seconds=120)

        result = {
            "api_path": api_path,
            "error_rate": error_rate,
            "threshold": self.settings.error_rate_threshold,
            "exceeded": error_rate >= self.settings.error_rate_threshold,
            "alerted": False,
        }

        if result["exceeded"]:
            result["alerted"] = self._maybe_alert(api_path, metrics)

        return result

    def _maybe_alert(self, api_path: str, metrics: dict) -> bool:
        """Send alert if cooldown period has passed."""
        last_alert = self.cache.get_last_alert_time(api_path)
        if last_alert:
            last_dt = datetime.fromisoformat(last_alert)
            cooldown = timedelta(minutes=self.settings.alert_cooldown_minutes)
            if datetime.utcnow() - last_dt < cooldown:
                logger.info("alert_cooldown_active", api_path=api_path)
                return False

        now = datetime.utcnow().isoformat()
        alert = {
            "api_path": api_path,
            "alert_type": "error_rate_exceeded",
            "error_rate": metrics["error_rate"],
            "threshold": self.settings.error_rate_threshold,
            "total_requests": metrics["total_requests"],
            "error_count": metrics["error_count"],
            "timestamp": now,
        }

        self.notifier.send_teams_alert(alert)
        self.db.store_alert(alert)
        self.cache.set_last_alert_time(api_path, now)
        logger.info("alert_sent", api_path=api_path, error_rate=metrics["error_rate"])
        return True

    def get_errors_by_status(self, hours_back: int = 1) -> dict:
        """Segregate errors by HTTP status code category."""
        categories = {}
        for status_code in [400, 401, 403, 404, 500, 502, 503, 504]:
            logs = self.cw.get_error_logs_by_status(status_code, hours_back)
            category = self.categorize_status(status_code)
            if category.value not in categories:
                categories[category.value] = []
            categories[category.value].append({
                "status_code": status_code,
                "count": len(logs),
                "samples": logs[:5],
            })
        return categories
