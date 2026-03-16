"""DynamoDB service with singleton resource and retry configuration."""
import boto3
import threading
import structlog
from datetime import datetime
from decimal import Decimal
from botocore.config import Config as BotoConfig
from app.config import get_settings

logger = structlog.get_logger()

_resource = None
_resource_lock = threading.Lock()


def _get_resource():
    global _resource
    if _resource is None:
        with _resource_lock:
            if _resource is None:
                settings = get_settings()
                _resource = boto3.resource(
                    "dynamodb", region_name=settings.aws_region,
                    config=BotoConfig(retries={"max_attempts": 3, "mode": "adaptive"}, max_pool_connections=25),
                )
    return _resource


class DynamoDBService:
    def __init__(self):
        res = _get_resource()
        prefix = get_settings().dynamodb_table_prefix
        self.alerts_table = res.Table(f"{prefix}-alerts")
        self.metrics_table = res.Table(f"{prefix}-metrics")
        self.audit_table = res.Table(f"{prefix}-audit")

    def ping(self) -> bool:
        try:
            self.alerts_table.table_status
            return True
        except Exception:
            return False

    @staticmethod
    def _decimalize(data: dict) -> dict:
        return {k: Decimal(str(v)) if isinstance(v, float) else v for k, v in data.items()}

    def store_alert(self, alert: dict) -> None:
        try:
            item = self._decimalize(alert)
            item["pk"] = f"ALERT#{alert['api_path']}"
            item["sk"] = datetime.utcnow().isoformat()
            self.alerts_table.put_item(Item=item)
        except Exception as e:
            logger.error("store_alert_failed", error=str(e))

    def store_metric_snapshot(self, metric: dict) -> None:
        try:
            item = self._decimalize(metric)
            api_path = metric.get("api_path", "unknown")
            item["pk"] = f"METRIC#{api_path}"
            item["sk"] = datetime.utcnow().isoformat()
            self.metrics_table.put_item(Item=item)
        except Exception as e:
            logger.error("store_metric_failed", error=str(e))

    def store_audit_log(self, audit: dict) -> None:
        try:
            item = self._decimalize(audit)
            item["pk"] = f"AUDIT#{audit.get('action', 'unknown')}"
            item["sk"] = datetime.utcnow().isoformat()
            self.audit_table.put_item(Item=item)
        except Exception as e:
            logger.error("store_audit_failed", error=str(e))

    def get_alerts(self, api_path: str, limit: int = 20) -> list[dict]:
        try:
            return self.alerts_table.query(
                KeyConditionExpression="pk = :pk",
                ExpressionAttributeValues={":pk": f"ALERT#{api_path}"},
                ScanIndexForward=False, Limit=limit,
            ).get("Items", [])
        except Exception as e:
            logger.error("get_alerts_failed", error=str(e))
            return []

    def get_metric_history(self, api_path: str, limit: int = 60) -> list[dict]:
        try:
            return self.metrics_table.query(
                KeyConditionExpression="pk = :pk",
                ExpressionAttributeValues={":pk": f"METRIC#{api_path}"},
                ScanIndexForward=False, Limit=limit,
            ).get("Items", [])
        except Exception as e:
            logger.error("get_metrics_failed", error=str(e))
            return []

    def get_audit_logs(self, action: str = None, limit: int = 50) -> list[dict]:
        try:
            if action:
                return self.audit_table.query(
                    KeyConditionExpression="pk = :pk",
                    ExpressionAttributeValues={":pk": f"AUDIT#{action}"},
                    ScanIndexForward=False, Limit=limit,
                ).get("Items", [])
            return self.audit_table.scan(Limit=limit).get("Items", [])
        except Exception as e:
            logger.error("get_audit_failed", error=str(e))
            return []
