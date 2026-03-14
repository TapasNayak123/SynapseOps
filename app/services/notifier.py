import httpx
import structlog
from app.config import get_settings

logger = structlog.get_logger()

ALERT_COLORS = {
    "error_rate_exceeded": "FF0000",
    "predictive_threshold_warning": "FFA500",
    "slow_api_detected": "FFD700",
    "traffic_anomaly_traffic_spike": "FF4500",
    "traffic_anomaly_traffic_drop": "4169E1",
    "recurring_error_detected": "DC143C",
    "sla_violation": "8B0000",
    "auto_fix_pr_created": "00AA00",
}

ALERT_ICONS = {
    "error_rate_exceeded": "🚨",
    "predictive_threshold_warning": "⚠️",
    "slow_api_detected": "🐢",
    "traffic_anomaly_traffic_spike": "📈",
    "traffic_anomaly_traffic_drop": "📉",
    "recurring_error_detected": "🔁",
    "sla_violation": "📋",
    "auto_fix_pr_created": "🔧",
}


class NotifierService:
    def __init__(self):
        self.settings = get_settings()

    def send_teams_alert(self, alert: dict) -> bool:
        """Send alert to Microsoft Teams via webhook."""
        if not self.settings.teams_webhook_url:
            logger.warning("teams_webhook_not_configured")
            return False

        alert_type = alert.get("alert_type", "unknown")
        color = ALERT_COLORS.get(alert_type, "FFA500")
        icon = ALERT_ICONS.get(alert_type, "🔔")
        title = f"{icon} {alert_type.replace('_', ' ').title()}"

        facts = [
            {"name": "API", "value": alert.get("api_path", "unknown")},
        ]

        # Add relevant facts based on alert type
        if alert.get("error_rate"):
            facts.append({"name": "Error Rate", "value": f"{alert['error_rate']:.1f}%"})
        if alert.get("threshold"):
            facts.append({"name": "Threshold", "value": f"{alert['threshold']}"})
        if alert.get("total_requests"):
            facts.append({"name": "Total Requests", "value": str(alert["total_requests"])})
        if alert.get("error_count"):
            facts.append({"name": "Error Count", "value": str(alert["error_count"])})
        if alert.get("extra"):
            facts.append({"name": "Details", "value": str(alert["extra"])})
        if alert.get("timestamp"):
            facts.append({"name": "Time", "value": alert["timestamp"]})

        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color,
            "summary": f"SynapseOps: {alert_type}",
            "sections": [
                {
                    "activityTitle": title,
                    "activitySubtitle": "SynapseOps Monitoring Agent",
                    "facts": facts,
                    "markdown": True,
                }
            ],
        }

        try:
            with httpx.Client() as client:
                resp = client.post(self.settings.teams_webhook_url, json=card, timeout=10)
                resp.raise_for_status()
            logger.info("teams_alert_sent", alert_type=alert_type, api_path=alert.get("api_path"))
            return True
        except Exception as e:
            logger.error("teams_alert_failed", error=str(e))
            return False
