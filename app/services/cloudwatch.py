"""CloudWatch Logs Insights service with automatic stream-scan fallback.

CloudWatch Logs Insights has an indexing delay (up to 5-30 min for recent logs).
Every public method that returns a list tries Insights first, then falls back to
scanning the raw log stream so recent data is never missed.
"""
import json as _json
import re
import time
import threading
import boto3
import structlog
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional, List, Dict
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


def _parse_event(event: Dict) -> Optional[Dict]:
    """Parse a raw CloudWatch log event into a structured dict."""
    try:
        data = _json.loads(event["message"])
        ts = datetime.utcfromtimestamp(event["timestamp"] / 1000).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        return {
            "@timestamp": ts,
            F_PATH: data.get(F_PATH, ""),
            F_METHOD: data.get(F_METHOD, ""),
            F_STATUS: str(data.get(F_STATUS, "")),
            F_DURATION: str(data.get(F_DURATION, "")),
            F_CORRELATION: data.get(F_CORRELATION, ""),
            F_MESSAGE: data.get(F_MESSAGE, ""),
            F_LEVEL: data.get(F_LEVEL, ""),
            F_ERROR_CODE: data.get(F_ERROR_CODE, ""),
            F_STACK: data.get(F_STACK, ""),
        }
    except (_json.JSONDecodeError, KeyError, TypeError):
        return None


class CloudWatchService:
    # ── In-memory cache for stream scan (shared across ALL instances, short TTL) ──
    # This is intentionally a class variable so all CloudWatchService instances
    # share the same cache. This is safe because all instances use the same log group
    # (configured via settings). If multiple log groups were needed, this would need
    # to be keyed by log_group.
    _stream_cache: List[Dict] = []
    _stream_cache_ts: float = 0
    _STREAM_CACHE_TTL = 60  # seconds

    def __init__(self):
        self.client = _get_client()
        settings = get_settings()
        self.log_group = settings.cloudwatch_log_group
        apis = [a.strip() for a in settings.monitored_apis.split(",") if a.strip()]
        self._monitored_apis = apis
        if apis:
            clauses = " or ".join(f'{F_PATH} like "{a}"' for a in apis)
            self._api_filter = f"({clauses})"
        else:
            self._api_filter = f'{F_PATH} like /^\\/api\\//'

    # ── Core query helpers ────────────────────────────────────────────────

    def _query(self, query: str, start: datetime, end: datetime, limit: int = 100) -> List[Dict]:
        try:
            resp = self.client.start_query(
                logGroupName=self.log_group,
                startTime=int(start.timestamp()),
                endTime=int(end.timestamp()),
                queryString=query,
                limit=min(limit, 10000),
            )
            qid = resp["queryId"]
            max_wait, elapsed = 30, 0
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

    def query_logs(self, query: str, hours_back: float = 1, limit: int = 100) -> List[Dict]:
        end = datetime.utcnow()
        return self._query(query, end - timedelta(hours=hours_back), end, limit)

    # ── Universal stream scan fallback ────────────────────────────────────

    def _get_recent_events(self, hours_back: float = 24) -> List[Dict]:
        """Fetch and cache recent parsed log events directly from streams.
        Bypasses Insights indexing delay. Cached for 60s to avoid repeated API calls."""
        now = time.time()
        if CloudWatchService._stream_cache and (now - CloudWatchService._stream_cache_ts) < self._STREAM_CACHE_TTL:
            return CloudWatchService._stream_cache
        try:
            start_ms = int((datetime.utcnow() - timedelta(hours=min(hours_back, 48))).timestamp() * 1000)
            resp = self.client.describe_log_streams(
                logGroupName=self.log_group, orderBy="LastEventTime", descending=True, limit=3,
            )
            all_events = []
            for stream in resp.get("logStreams", []):
                events_resp = self.client.get_log_events(
                    logGroupName=self.log_group,
                    logStreamName=stream["logStreamName"],
                    startTime=start_ms, startFromHead=False, limit=1000,
                )
                for raw in events_resp.get("events", []):
                    parsed = _parse_event(raw)
                    if parsed:
                        all_events.append(parsed)
            all_events.sort(key=lambda e: e["@timestamp"], reverse=True)
            CloudWatchService._stream_cache = all_events
            CloudWatchService._stream_cache_ts = now
            return all_events
        except Exception as e:
            logger.warning("stream_scan_failed", error=str(e))
            return []

    def _matches_api_filter(self, event: dict) -> bool:
        """Check if an event matches the monitored APIs filter."""
        p = event.get(F_PATH, "")
        if not p:
            return False
        if self._monitored_apis:
            return any(api in p for api in self._monitored_apis)
        return p.startswith("/api/")

    def _is_response_event(self, event: dict) -> bool:
        """Check if event is a completed request (not 'Request started')."""
        m = event.get(F_MESSAGE, "")
        return m in ("Request completed", "Error occurred")

    # ── Public query methods (all with stream-scan fallback) ──────────────

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
            # Fallback: compute from stream
            events = [e for e in self._get_recent_events(period_minutes / 60)
                      if path in e.get(F_PATH, "") and self._is_response_event(e)]
            total = len(events)
            errors = sum(1 for e in events if int(e.get(F_STATUS, 0) or 0) >= 500)
            client_errors = sum(1 for e in events if 400 <= int(e.get(F_STATUS, 0) or 0) < 500)
        return {
            "api_path": api_path, "total_requests": total, "error_count": errors,
            "client_error_count": client_errors,
            "total_error_count": errors + client_errors,
            "error_rate": ((errors + client_errors) / total * 100) if total else 0.0,
            "server_error_rate": (errors / total * 100) if total else 0.0,
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
        # Fallback
        events = [e for e in self._get_recent_events(period_minutes / 60)
                  if path in e.get(F_PATH, "") and e.get(F_MESSAGE) == "Request completed"]
        durations = []
        for e in events:
            d = e.get(F_DURATION, "")
            m = re.search(r'\d+', str(d))
            if m:
                durations.append(int(m.group()))
        if durations:
            durations.sort()
            p99_idx = max(0, int(len(durations) * 0.99) - 1)
            return {"api_path": api_path, "avg_latency_ms": sum(durations) / len(durations),
                    "max_latency_ms": max(durations), "p99_latency_ms": durations[p99_idx]}
        return {"api_path": api_path, "avg_latency_ms": 0, "max_latency_ms": 0, "p99_latency_ms": 0}

    def get_error_logs_by_status(self, status_code: int, hours_back: int = 1) -> List[Dict]:
        query = f"""fields @timestamp, {F_PATH}, {F_METHOD}, {F_STATUS}, {F_CORRELATION}, {F_MESSAGE}, {F_ERROR_CODE}, {F_STACK}
| filter {F_STATUS} = {status_code} and {self._api_filter} | sort @timestamp desc | limit 50"""
        results = self.query_logs(query, hours_back)
        if results:
            return results
        return [e for e in self._get_recent_events(hours_back)
                if e.get(F_STATUS) == str(status_code) and self._matches_api_filter(e)][:50]

    def get_logs_by_correlation_id(self, cid: str, hours_back: float = 24) -> List[Dict]:
        safe = _sanitize(cid)
        if not safe:
            return []
        query = f"""fields @timestamp, {F_PATH}, {F_METHOD}, {F_STATUS}, {F_DURATION}, {F_CORRELATION}, {F_MESSAGE}, {F_LEVEL}, {F_ERROR_CODE}, {F_STACK}
| filter {F_CORRELATION} = "{safe}" | sort @timestamp asc | limit 200"""
        results = self.query_logs(query, hours_back)
        if results:
            return results
        # Fallback: scan stream for this correlation ID
        matches = [e for e in self._get_recent_events(hours_back) if safe in e.get(F_CORRELATION, "")]
        matches.sort(key=lambda e: e["@timestamp"])
        return matches

    def get_top_apis(self, hours_back: int = 1, limit: int = 10) -> List[Dict]:
        query = f"""fields {F_PATH}, {F_METHOD} | filter {F_RESPONSE_FILTER} and {self._api_filter}
| stats count(*) as request_count by {F_PATH}, {F_METHOD} | sort request_count desc | limit {limit}"""
        results = self.query_logs(query, hours_back)
        if results:
            return results
        # Fallback: aggregate from stream
        events = [e for e in self._get_recent_events(hours_back)
                  if self._matches_api_filter(e) and self._is_response_event(e)]
        counts = Counter((e.get(F_PATH, ""), e.get(F_METHOD, "")) for e in events)
        return [
            {F_PATH: path, F_METHOD: method, "request_count": str(cnt)}
            for (path, method), cnt in counts.most_common(limit)
        ]

    def get_slowest_apis(self, hours_back: int = 1, limit: int = 10) -> List[Dict]:
        query = f"""fields {F_PATH}, {F_METHOD}, {F_DURATION}
| filter {F_MESSAGE} = "Request completed" and ispresent({F_DURATION}) and {self._api_filter}
| parse {F_DURATION} /(?<d>\\d+)/
| stats avg(d) as avg_latency, max(d) as max_latency, count(*) as request_count by {F_PATH}, {F_METHOD}
| sort avg_latency desc | limit {limit}"""
        results = self.query_logs(query, hours_back)
        if results:
            return results
        # Fallback
        events = [e for e in self._get_recent_events(hours_back)
                  if self._matches_api_filter(e) and e.get(F_MESSAGE) == "Request completed"]
        api_durations: dict[tuple, list[int]] = {}
        for e in events:
            d = e.get(F_DURATION, "")
            m = re.search(r'\d+', str(d))
            if m:
                key = (e.get(F_PATH, ""), e.get(F_METHOD, ""))
                api_durations.setdefault(key, []).append(int(m.group()))
        rows = []
        for (path, method), durs in api_durations.items():
            rows.append({
                F_PATH: path, F_METHOD: method,
                "avg_latency": str(round(sum(durs) / len(durs), 1)),
                "max_latency": str(max(durs)),
                "request_count": str(len(durs)),
            })
        rows.sort(key=lambda r: float(r["avg_latency"]), reverse=True)
        return rows[:limit]

    def get_api_history(self, api_path: str, hours_back: int = 24) -> List[Dict]:
        path = _sanitize(api_path)
        if not path:
            return []
        query = f"""fields @timestamp, {F_STATUS}, {F_DURATION}, {F_CORRELATION}, {F_METHOD}, {F_ERROR_CODE}, {F_LEVEL}
| filter {F_PATH} like "{path}" and {F_RESPONSE_FILTER} and {self._api_filter} | sort @timestamp desc | limit 100"""
        results = self.query_logs(query, hours_back)
        if results:
            return results
        return [e for e in self._get_recent_events(hours_back)
                if path in e.get(F_PATH, "") and self._is_response_event(e)][:100]

    def get_error_logs(self, hours_back: int = 1) -> List[Dict]:
        query = f"""fields @timestamp, {F_PATH}, {F_METHOD}, {F_STATUS}, {F_CORRELATION}, {F_MESSAGE}, {F_ERROR_CODE}, {F_STACK}, {F_LEVEL}
| filter ({F_LEVEL} = "error" or {F_STATUS} >= 400) and {self._api_filter} | sort @timestamp desc | limit 100"""
        results = self.query_logs(query, hours_back)
        if results:
            return results
        return [e for e in self._get_recent_events(hours_back)
                if self._matches_api_filter(e) and (
                    e.get(F_LEVEL) == "error" or int(e.get(F_STATUS, 0) or 0) >= 400
                )][:100]
