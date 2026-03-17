"""CloudWatch Logs Insights service for querying application logs."""
import re
import time
import threading
import boto3
import structlog
from datetime import datetime, timedelta
from botocore.config import Config as BotoConfig
from app.config import get_settings

logger = structlog.get_logger()

# Log field mapping for Node.js app
F_PATH = "path"
F_METHOD = "method"
F_STATUS = "statusCode"
F_DURATION = "duration"
F_CORRELATION = "correlationId"
F_MESSAGE = "message"
F_LEVEL = "level"
F_ERROR_CODE = "errorCode"
F_STACK = "stack"
F_RESPONSE_FILTER = f'({F_MESSAGE} = "Request completed" or {F_MESSAGE} = "Error occurred")'

# Singleton client
_client = None
_client_lock = threading.Lock()


def _get_client():
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                settings = get_settings()
                _client = boto3.client(
                    "logs",
                    region_name=settings.aws_region,
                    config=BotoConfig(retries={"max_attempts": 3, "mode": "adaptive"}, connect_timeout=5, read_timeout=30),
                )
    return _client


def _sanitize(value: str) -> str:
    """Sanitize input for CloudWatch queries."""
    if not value:
        return ""
    return re.sub(r'["\'\\\n\r\t|;]', '', value)[:500]


class CloudWatchService:
    def __init__(self):
        self.client = _get_client()
        settings = get_settings()
        self.log_group = settings.cloudwatch_log_group
        # Build a reusable CloudWatch filter clause from MONITORED_APIS
        apis = [a.strip() for a in settings.monitored_apis.split(",") if a.strip()]
        if apis:
            # e.g. (path = "/api/auth/register" or path = "/api/auth/login" or path = "/api/products")
            clauses = " or ".join(f'{F_PATH} like "{a}"' for a in apis)
            self._api_filter = f"({clauses})"
        else:
            # Fallback: only /api/* paths
            self._api_filter = f'{F_PATH} like /^\\/api\\//'

    def _query(self, query: str, start: datetime, end: datetime, limit: int = 100) -> list[dict]:
        try:
            resp = self.client.start_query(
                logGroupName=self.log_group,
                startTime=int(start.timestamp()),
                endTime=int(end.timestamp()),
                queryString=query,
                limit=min(limit, 10000),  # CloudWatch max is 10000
            )
            qid = resp["queryId"]
            # Poll with timeout to prevent infinite hang
            max_wait = 30  # seconds
            elapsed = 0
            while elapsed < max_wait:
                result = self.client.get_query_results(queryId=qid)
                if result["status"] in ("Complete", "Failed", "Cancelled"):
                    break
                time.sleep(0.5)
                elapsed += 0.5
            else:
                logger.warning("query_timeout", query_id=qid)
                return []
            if result["status"] != "Complete":
                logger.warning("query_incomplete", status=result["status"])
                return []
            return [{f["field"]: f["value"] for f in row} for row in result.get("results", [])]
        except Exception as e:
            logger.error("query_failed", error=str(e))
            return []

    def query_logs(self, query: str, hours_back: int = 1, limit: int = 100) -> list[dict]:
        end = datetime.utcnow()
        return self._query(query, end - timedelta(hours=hours_back), end, limit)

    def get_api_metrics(self, api_path: str, period_minutes: int = 60) -> dict:
        path = _sanitize(api_path)
        if not path:
            return {"api_path": api_path, "total_requests": 0, "error_count": 0, "error_rate": 0.0}
        end = datetime.utcnow()
        start = end - timedelta(minutes=period_minutes)
        query = f"""fields {F_PATH}, {F_STATUS}
| filter {F_PATH} like "{path}" and {F_RESPONSE_FILTER} and {self._api_filter}
| stats count(*) as total, sum({F_STATUS} >= 500) as errors, sum({F_STATUS} >= 400 and {F_STATUS} < 500) as client_errors"""
        results = self._query(query, start, end, 1)
        if results:
            total = int(results[0].get("total", 0))
            errors = int(results[0].get("errors", 0))
            client_errors = int(results[0].get("client_errors", 0))
        else:
            total, errors, client_errors = 0, 0, 0
        return {
            "api_path": api_path, "total_requests": total, "error_count": errors,
            "client_error_count": client_errors, "error_rate": (errors / total * 100) if total else 0.0,
            "start_time": start.isoformat(), "end_time": end.isoformat(),
        }

    def get_latency_metrics(self, api_path: str, period_minutes: int = 5) -> dict:
        path = _sanitize(api_path)
        if not path:
            return {"api_path": api_path, "avg_latency_ms": 0, "max_latency_ms": 0, "p99_latency_ms": 0}
        end = datetime.utcnow()
        query = f"""fields {F_PATH}, {F_DURATION}
| filter {F_PATH} like "{path}" and {F_MESSAGE} = "Request completed" and {self._api_filter}
| parse {F_DURATION} /(?<d>\\d+)/
| stats avg(d) as avg, max(d) as max, pct(d, 99) as p99"""
        results = self._query(query, end - timedelta(minutes=period_minutes), end, 1)
        if results:
            return {"api_path": api_path, "avg_latency_ms": float(results[0].get("avg", 0)),
                    "max_latency_ms": float(results[0].get("max", 0)), "p99_latency_ms": float(results[0].get("p99", 0))}
        return {"api_path": api_path, "avg_latency_ms": 0, "max_latency_ms": 0, "p99_latency_ms": 0}

    def get_error_logs_by_status(self, status_code: int, hours_back: int = 1) -> list[dict]:
        query = f"""fields @timestamp, {F_PATH}, {F_METHOD}, {F_STATUS}, {F_CORRELATION}, {F_MESSAGE}, {F_ERROR_CODE}, {F_STACK}
| filter {F_STATUS} = {status_code} and {self._api_filter} | sort @timestamp desc | limit 50"""
        return self.query_logs(query, hours_back)

    def get_logs_by_correlation_id(self, cid: str) -> list[dict]:
        safe = _sanitize(cid)
        if not safe:
            return []
        query = f"""fields @timestamp, {F_PATH}, {F_METHOD}, {F_STATUS}, {F_DURATION}, {F_CORRELATION}, {F_MESSAGE}, {F_LEVEL}, {F_ERROR_CODE}, {F_STACK}
| filter {F_CORRELATION} = "{safe}" | sort @timestamp asc | limit 200"""
        return self.query_logs(query, 24)

    def get_top_apis(self, hours_back: int = 1, limit: int = 10) -> list[dict]:
        query = f"""fields {F_PATH}, {F_METHOD} | filter {F_RESPONSE_FILTER} and {self._api_filter}
| stats count(*) as request_count by {F_PATH}, {F_METHOD} | sort request_count desc | limit {limit}"""
        return self.query_logs(query, hours_back)

    def get_slowest_apis(self, hours_back: int = 1, limit: int = 10) -> list[dict]:
        query = f"""fields {F_PATH}, {F_METHOD}, {F_DURATION}
| filter {F_MESSAGE} = "Request completed" and ispresent({F_DURATION}) and {self._api_filter}
| parse {F_DURATION} /(?<d>\\d+)/
| stats avg(d) as avg_latency, max(d) as max_latency, count(*) as request_count by {F_PATH}, {F_METHOD}
| sort avg_latency desc | limit {limit}"""
        return self.query_logs(query, hours_back)

    def get_api_history(self, api_path: str, hours_back: int = 24) -> list[dict]:
        path = _sanitize(api_path)
        if not path:
            return []
        query = f"""fields @timestamp, {F_STATUS}, {F_DURATION}, {F_CORRELATION}, {F_METHOD}, {F_ERROR_CODE}, {F_LEVEL}
| filter {F_PATH} like "{path}" and {F_RESPONSE_FILTER} and {self._api_filter} | sort @timestamp desc | limit 100"""
        return self.query_logs(query, hours_back)

    def get_error_logs(self, hours_back: int = 1) -> list[dict]:
        query = f"""fields @timestamp, {F_PATH}, {F_METHOD}, {F_STATUS}, {F_CORRELATION}, {F_MESSAGE}, {F_ERROR_CODE}, {F_STACK}, {F_LEVEL}
| filter ({F_LEVEL} = "error" or {F_STATUS} >= 500) and {self._api_filter} | sort @timestamp desc | limit 100"""
        return self.query_logs(query, hours_back)
