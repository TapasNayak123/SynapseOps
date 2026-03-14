import boto3
import structlog
from datetime import datetime, timedelta
from app.config import get_settings

logger = structlog.get_logger()


class CloudWatchService:
    def __init__(self):
        settings = get_settings()
        self.cw_client = boto3.client("cloudwatch", region_name=settings.aws_region)
        self.logs_client = boto3.client("logs", region_name=settings.aws_region)
        self.namespace = settings.cloudwatch_namespace
        self.log_group = settings.cloudwatch_log_group

    def get_api_metrics(self, api_path: str, period_minutes: int = 1) -> dict:
        """Fetch error count and request count for an API over a period."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=period_minutes)

        try:
            response = self.cw_client.get_metric_statistics(
                Namespace=self.namespace,
                MetricName="RequestCount",
                Dimensions=[{"Name": "ApiPath", "Value": api_path}],
                StartTime=start_time,
                EndTime=end_time,
                Period=period_minutes * 60,
                Statistics=["Sum"],
            )
            total = sum(dp["Sum"] for dp in response.get("Datapoints", []))

            response = self.cw_client.get_metric_statistics(
                Namespace=self.namespace,
                MetricName="ErrorCount",
                Dimensions=[{"Name": "ApiPath", "Value": api_path}],
                StartTime=start_time,
                EndTime=end_time,
                Period=period_minutes * 60,
                Statistics=["Sum"],
            )
            errors = sum(dp["Sum"] for dp in response.get("Datapoints", []))

            return {
                "api_path": api_path,
                "total_requests": int(total),
                "error_count": int(errors),
                "error_rate": (errors / total * 100) if total > 0 else 0.0,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
            }
        except Exception as e:
            logger.error("cloudwatch_metric_fetch_failed", api_path=api_path, error=str(e))
            return {"api_path": api_path, "total_requests": 0, "error_count": 0, "error_rate": 0.0}

    def get_latency_metrics(self, api_path: str, period_minutes: int = 5) -> dict:
        """Fetch latency percentiles for an API."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=period_minutes)

        try:
            response = self.cw_client.get_metric_statistics(
                Namespace=self.namespace,
                MetricName="Latency",
                Dimensions=[{"Name": "ApiPath", "Value": api_path}],
                StartTime=start_time,
                EndTime=end_time,
                Period=period_minutes * 60,
                Statistics=["Average", "Maximum"],
                ExtendedStatistics=["p99"],
            )
            datapoints = response.get("Datapoints", [])
            if not datapoints:
                return {"api_path": api_path, "avg_latency_ms": 0, "p99_latency_ms": 0}

            dp = datapoints[0]
            return {
                "api_path": api_path,
                "avg_latency_ms": dp.get("Average", 0),
                "max_latency_ms": dp.get("Maximum", 0),
                "p99_latency_ms": dp.get("ExtendedStatistics", {}).get("p99", 0),
            }
        except Exception as e:
            logger.error("cloudwatch_latency_fetch_failed", api_path=api_path, error=str(e))
            return {"api_path": api_path, "avg_latency_ms": 0, "p99_latency_ms": 0}

    def query_logs(self, query: str, hours_back: int = 1, limit: int = 100) -> list[dict]:
        """Run a CloudWatch Logs Insights query."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)

        try:
            response = self.logs_client.start_query(
                logGroupName=self.log_group,
                startTime=int(start_time.timestamp()),
                endTime=int(end_time.timestamp()),
                queryString=query,
                limit=limit,
            )
            query_id = response["queryId"]

            import time
            while True:
                result = self.logs_client.get_query_results(queryId=query_id)
                if result["status"] in ("Complete", "Failed", "Cancelled"):
                    break
                time.sleep(0.5)

            if result["status"] != "Complete":
                logger.warning("log_query_incomplete", status=result["status"])
                return []

            return [
                {field["field"]: field["value"] for field in row}
                for row in result.get("results", [])
            ]
        except Exception as e:
            logger.error("log_query_failed", error=str(e))
            return []

    def get_error_logs_by_status(self, status_code: int, hours_back: int = 1) -> list[dict]:
        """Get error logs filtered by HTTP status code."""
        query = f"""
            fields @timestamp, @message, @logStream
            | filter status_code = {status_code}
            | sort @timestamp desc
            | limit 50
        """
        return self.query_logs(query, hours_back)

    def get_logs_by_correlation_id(self, correlation_id: str) -> list[dict]:
        """Trace a request using correlation ID."""
        query = f"""
            fields @timestamp, @message, @logStream
            | filter correlation_id = "{correlation_id}"
            | sort @timestamp asc
            | limit 200
        """
        return self.query_logs(query, hours_back=24)

    def get_top_apis(self, hours_back: int = 1, limit: int = 10) -> list[dict]:
        """Get top N APIs by request count."""
        query = f"""
            fields api_path, method
            | stats count(*) as request_count by api_path, method
            | sort request_count desc
            | limit {limit}
        """
        return self.query_logs(query, hours_back)

    def get_slowest_apis(self, hours_back: int = 1, limit: int = 10) -> list[dict]:
        """Get slowest APIs by average latency."""
        query = f"""
            fields api_path, method, duration_ms
            | stats avg(duration_ms) as avg_latency, max(duration_ms) as max_latency,
                    count(*) as request_count by api_path, method
            | sort avg_latency desc
            | limit {limit}
        """
        return self.query_logs(query, hours_back)

    def get_api_history(self, api_path: str, hours_back: int = 24) -> list[dict]:
        """Get request history for a specific API."""
        query = f"""
            fields @timestamp, status_code, duration_ms, correlation_id
            | filter api_path = "{api_path}"
            | sort @timestamp desc
            | limit 100
        """
        return self.query_logs(query, hours_back)
