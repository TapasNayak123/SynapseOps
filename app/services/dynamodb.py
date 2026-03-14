import boto3
import structlog
from datetime import datetime
from decimal import Decimal
from app.config import get_settings

logger = structlog.get_logger()


class DynamoDBService:
    def __init__(self):
        settings = get_settings()
        self.dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
        self.prefix = settings.dynamodb_table_prefix
        self.alerts_table = self.dynamodb.Table(f"{self.prefix}-alerts")
        self.metrics_table = self.dynamodb.Table(f"{self.prefix}-metrics")
        self.audit_table = self.dynamodb.Table(f"{self.prefix}-audit")

    def _to_decimal(self, data: dict) -> dict:
        """Convert floats to Decimal for DynamoDB."""
        return {
            k: Decimal(str(v)) if isinstance(v, float) else v
            for k, v in data.items()
        }

    def store_alert(self, alert: dict) -> None:
        try:
            item = self._to_decimal(alert)
            item["pk"] = f"ALERT#{alert['api_path']}"
            item["sk"] = datetime.utcnow().isoformat()
            self.alerts_table.put_item(Item=item)
        except Exception as e:
            logger.error("dynamodb_store_alert_failed", error=str(e))

    def store_metric_snapshot(self, metric: dict) -> None:
        try:
            item = self._to_decimal(metric)
            item["pk"] = f"METRIC#{metric['api_path']}"
            item["sk"] = datetime.utcnow().isoformat()
            self.metrics_table.put_item(Item=item)
        except Exception as e:
            logger.error("dynamodb_store_metric_failed", error=str(e))

    def store_audit_log(self, audit: dict) -> None:
        try:
            item = self._to_decimal(audit)
            item["pk"] = f"AUDIT#{audit.get('action', 'unknown')}"
            item["sk"] = datetime.utcnow().isoformat()
            self.audit_table.put_item(Item=item)
        except Exception as e:
            logger.error("dynamodb_store_audit_failed", error=str(e))

    def get_alerts(self, api_path: str, limit: int = 20) -> list[dict]:
        try:
            response = self.alerts_table.query(
                KeyConditionExpression="pk = :pk",
                ExpressionAttributeValues={":pk": f"ALERT#{api_path}"},
                ScanIndexForward=False,
                Limit=limit,
            )
            return response.get("Items", [])
        except Exception as e:
            logger.error("dynamodb_get_alerts_failed", error=str(e))
            return []

    def get_metric_history(self, api_path: str, limit: int = 60) -> list[dict]:
        try:
            response = self.metrics_table.query(
                KeyConditionExpression="pk = :pk",
                ExpressionAttributeValues={":pk": f"METRIC#{api_path}"},
                ScanIndexForward=False,
                Limit=limit,
            )
            return response.get("Items", [])
        except Exception as e:
            logger.error("dynamodb_get_metrics_failed", error=str(e))
            return []

    def get_audit_logs(self, action: str = None, limit: int = 50) -> list[dict]:
        try:
            if action:
                response = self.audit_table.query(
                    KeyConditionExpression="pk = :pk",
                    ExpressionAttributeValues={":pk": f"AUDIT#{action}"},
                    ScanIndexForward=False,
                    Limit=limit,
                )
            else:
                response = self.audit_table.scan(Limit=limit)
            return response.get("Items", [])
        except Exception as e:
            logger.error("dynamodb_get_audit_failed", error=str(e))
            return []
