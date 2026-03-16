"""Predictive alerting (linear regression) and traffic anomaly detection (z-score)."""
import math
import structlog
from datetime import datetime
from app.services.dynamodb import DynamoDBService
from app.services.cache import CacheService
from app.services.notifier import NotifierService
from app.config import get_settings

logger = structlog.get_logger()


class AnomalyDetector:
    def __init__(self):
        self.db = DynamoDBService()
        self.cache = CacheService()
        self.notifier = NotifierService()
        self.settings = get_settings()

    def predict_error_trend(self, api_path: str, lookback_minutes: int = 30) -> dict:
        history = self.db.get_metric_history(api_path, limit=lookback_minutes)
        if len(history) < 5:
            return {"api_path": api_path, "prediction": "insufficient_data", "datapoints": len(history)}

        rates = [(i, float(item.get("error_rate", 0))) for i, item in enumerate(reversed(history))]
        n = len(rates)
        sx = sum(r[0] for r in rates)
        sy = sum(r[1] for r in rates)
        sxy = sum(r[0] * r[1] for r in rates)
        sx2 = sum(r[0] ** 2 for r in rates)
        denom = n * sx2 - sx ** 2
        if denom == 0:
            return {"api_path": api_path, "prediction": "flat_trend", "slope": 0}

        slope = (n * sxy - sx * sy) / denom
        current = rates[-1][1]
        threshold = self.settings.error_rate_threshold

        result = {"api_path": api_path, "current_error_rate": current, "slope_per_minute": round(slope, 4),
                  "trend": "increasing" if slope > 0.5 else "decreasing" if slope < -0.5 else "stable",
                  "threshold": threshold}

        if slope > 0 and current < threshold:
            mins = (threshold - current) / slope
            result.update(predicted_breach_in_minutes=round(mins, 1), prediction="approaching_threshold")
            if mins <= 20:
                result["severity"] = "warning"
                self.notifier.send_teams_alert({
                    "api_path": api_path, "alert_type": "predictive_threshold_warning",
                    "error_rate": current, "threshold": threshold,
                    "timestamp": datetime.utcnow().isoformat(),
                    "extra": f"Trending toward {threshold}% in ~{round(mins)} min",
                })
        elif current >= threshold:
            result["prediction"] = "already_exceeded"
        else:
            result["prediction"] = "safe"
        return result

    def detect_traffic_anomaly(self, api_path: str, lookback_minutes: int = 60) -> dict:
        history = self.db.get_metric_history(api_path, limit=lookback_minutes)
        if len(history) < 10:
            return {"api_path": api_path, "anomaly": "insufficient_data"}

        counts = [int(item.get("total_requests", 0)) for item in reversed(history)]
        current = counts[-1]
        baseline = counts[:-1]
        mean = sum(baseline) / len(baseline)
        std = math.sqrt(sum((x - mean) ** 2 for x in baseline) / len(baseline)) or 1
        z = (current - mean) / std

        result = {"api_path": api_path, "current_requests": current, "baseline_mean": round(mean, 1),
                  "z_score": round(z, 2), "anomaly": "none"}

        if abs(z) > 2.5:
            result["anomaly"] = "traffic_spike" if z > 0 else "traffic_drop"
            result["severity"] = "high" if abs(z) > 3.5 else "medium"
            self.notifier.send_teams_alert({
                "api_path": api_path, "alert_type": f"traffic_anomaly_{result['anomaly']}",
                "total_requests": current, "timestamp": datetime.utcnow().isoformat(),
                "extra": f"Z-score: {round(z, 2)}, Baseline: {round(mean, 1)}",
            })
            self.db.store_alert({"api_path": api_path, "alert_type": result["anomaly"],
                                 "z_score": z, "timestamp": datetime.utcnow().isoformat()})
        return result
