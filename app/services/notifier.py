"""Microsoft Teams notification service via Power Automate webhook."""
import httpx
import threading
import structlog
from typing import Optional
from app.config import get_settings

logger = structlog.get_logger()

ICONS = {
    "error_rate_exceeded": "🚨", "predictive_threshold_warning": "⚠️", "slow_api_detected": "🐢",
    "traffic_anomaly_traffic_spike": "📈", "traffic_anomaly_traffic_drop": "📉",
    "recurring_error_detected": "🔁", "sla_violation": "📋", "auto_fix_pr_created": "🔧",
}

_http: Optional[httpx.Client] = None
_http_lock = threading.Lock()


def _get_http() -> httpx.Client:
    global _http
    if _http is None:
        with _http_lock:
            if _http is None:
                _http = httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0), limits=httpx.Limits(max_connections=10))
    return _http


def _reset_http() -> None:
    """Reset HTTP client on connection errors so next call gets a fresh one."""
    global _http
    with _http_lock:
        _http = None


class NotifierService:
    def __init__(self):
        self.webhook_url = get_settings().teams_webhook_url

    def send_teams_alert(self, alert: dict) -> bool:
        if not self.webhook_url:
            return False

        alert_type = alert.get("alert_type", "unknown")
        icon = ICONS.get(alert_type, "🔔")
        title = f"{icon} {alert_type.replace('_', ' ').title()}"

        facts = [{"title": "API", "value": alert.get("api_path", "unknown")}]
        if alert.get("error_rate"):
            facts.append({"title": "Error Rate", "value": f"{alert['error_rate']:.1f}%"})
        if alert.get("threshold"):
            facts.append({"title": "Threshold", "value": str(alert["threshold"])})
        if alert.get("total_requests"):
            facts.append({"title": "Requests", "value": str(alert["total_requests"])})
        if alert.get("extra"):
            facts.append({"title": "Details", "value": str(alert["extra"])})
        if alert.get("timestamp"):
            facts.append({"title": "Time", "value": alert["timestamp"]})

        payload = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard", "version": "1.4",
                    "body": [
                        {"type": "TextBlock", "text": title, "size": "Large", "weight": "Bolder"},
                        {"type": "TextBlock", "text": "SynapseOps Agent", "size": "Small", "isSubtle": True},
                        {"type": "FactSet", "facts": facts},
                    ],
                },
            }],
        }

        try:
            resp = _get_http().post(self.webhook_url, json=payload, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            logger.info("teams_alert_sent", alert_type=alert_type)
            return True
        except httpx.HTTPStatusError as e:
            logger.error("teams_alert_http_error", status=e.response.status_code, error=str(e))
            return False
        except Exception as e:
            logger.error("teams_alert_failed", error=str(e))
            _reset_http()
            return False
