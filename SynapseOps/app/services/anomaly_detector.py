"""
Predictive alerting and traffic anomaly detection.
Uses linear regression on error rate trends and z-score for traffic anomalies.
"""
import math
import structlog
from datetime import datetime
from app.services.cloudwatch import CloudWatchService
from app.services.dynamodb import DynamoDBService
from app.services.cache import CacheService
from app.services.notifier import NotifierService
from app.config import get_settings

logger = structlog.get_logger()


class AnomalyDetector:
    def __init__(self):
        self.cw = CloudWatchService()
        self.db = DynamoDBService()
        self.cache = CacheService()
        self.notifier = NotifierService()
        self.settings = get_settings()

    def predict_error_trend(self, api_path: str, lookback_minutes: int = 30) -> dict:
        """
        Use linear regression on recent error rate datapoints to predict
        when the threshold will be breached.
        """
        history = self.db.get_metric_history(api_path, limit=lookback_minutes)
        if len(history) < 5:
            return {
                "api_path": api_path,
                "prediction": "insufficient_data",
                "datapoints": len(history),
            }

        # Extract error rates with time indices
        rates = []
        for i, item in enumerate(reversed(history)):
            er = float(item.get("error_rate", 0))
            rates.append((i, er))

        # Simple linear regression: y = mx + b
        n = len(rates)
        sum_x = sum(r[0] for r in rates)
        sum_y = sum(r[1] for r in rates)
        sum_xy = sum(r[0] * r[1] for r in rates)
        sum_x2 = sum(r[0] ** 2 for r in rates)

        denominator = (n * sum_x2 - sum_x ** 2)
        if denominator == 0:
            return {"api_path": api_path, "prediction": "flat_trend", "slope": 0}

        slope = (n * sum_xy - sum_x * sum_y) / denominator
        intercept = (sum_y - slope * sum_x) / n
        current_rate = rates[-1][1]

        result = {
            "api_path": api_path,
            "current_error_rate": current_rate,
            "slope_per_minute": round(slope, 4),
            "trend": "increasing" if slope > 0.5 else "decreasing" if slope < -0.5 else "stable",
            "threshold": self.settings.error_rate_threshold,
        }

        # Predict when threshold will be breached
        if slope > 0 and current_rate < self.settings.error_rate_threshold:
            minutes_to_breach = (self.settings.error_rate_threshold - current_rate) / slope
            result["predicted_breach_in_minutes"] = round(minutes_to_breach, 1)
            result["prediction"] = "approaching_threshold"

            if minutes_to_breach <= 20:
                result["severity"] = "warning"
                self.notifier.send_teams_alert({
                    "api_path": api_path,
                    "alert_type": "predictive_threshold_warning",
                    "error_rate": current_rate,
                    "threshold": self.settings.error_rate_threshold,
                    "total_requests": 0,
                    "error_count": 0,
                    "timestamp": datetime.utcnow().isoformat(),
                    "extra": f"Error rate trending toward {self.settings.error_rate_threshold}% in ~{round(minutes_to_breach)} minutes",
                })
        elif current_rate >= self.settings.error_rate_threshold:
            result["prediction"] = "already_exceeded"
        else:
            result["prediction"] = "safe"

        return result

    def detect_traffic_anomaly(self, api_path: str, lookback_minutes: int = 60) -> dict:
        """
        Detect unusual spikes or drops in request volume using z-score.
        Z-score > 2 = spike, Z-score < -2 = drop.
        """
        history = self.db.get_metric_history(api_path, limit=lookback_minutes)
        if len(history) < 10:
            return {"api_path": api_path, "anomaly": "insufficient_data"}

        counts = [int(item.get("total_requests", 0)) for item in reversed(history)]
        current = counts[-1]

        # Calculate mean and std deviation (excluding current)
        baseline = counts[:-1]
        mean = sum(baseline) / len(baseline)
        variance = sum((x - mean) ** 2 for x in baseline) / len(baseline)
        std_dev = math.sqrt(variance) if variance > 0 else 1

        z_score = (current - mean) / std_dev

        result = {
            "api_path": api_path,
            "current_requests": current,
            "baseline_mean": round(mean, 1),
            "baseline_std_dev": round(std_dev, 1),
            "z_score": round(z_score, 2),
            "anomaly": "none",
        }

        if z_score > 2.5:
            result["anomaly"] = "traffic_spike"
            result["severity"] = "high" if z_score > 3.5 else "medium"
            self._alert_anomaly(api_path, result)
        elif z_score < -2.5:
            result["anomaly"] = "traffic_drop"
            result["severity"] = "high" if z_score < -3.5 else "medium"
            self._alert_anomaly(api_path, result)

        return result

    def _alert_anomaly(self, api_path: str, anomaly_data: dict) -> None:
        """Send Teams alert for traffic anomaly."""
        self.notifier.send_teams_alert({
            "api_path": api_path,
            "alert_type": f"traffic_anomaly_{anomaly_data['anomaly']}",
            "error_rate": 0,
            "threshold": 0,
            "total_requests": anomaly_data["current_requests"],
            "error_count": 0,
            "timestamp": datetime.utcnow().isoformat(),
            "extra": f"Z-score: {anomaly_data['z_score']}, Baseline mean: {anomaly_data['baseline_mean']}",
        })
        self.db.store_alert({
            "api_path": api_path,
            "alert_type": anomaly_data["anomaly"],
            "z_score": anomaly_data["z_score"],
            "timestamp": datetime.utcnow().isoformat(),
        })
