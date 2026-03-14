"""
Log analysis using CloudWatch Logs Insights (no OpenSearch dependency).
Handles correlation ID tracing, error search, top APIs, API history.
"""
import structlog
from app.services.cloudwatch import CloudWatchService

logger = structlog.get_logger()


class LogAnalyzer:
    def __init__(self):
        self.cw = CloudWatchService()

    def search_by_correlation_id(self, correlation_id: str) -> list[dict]:
        """Trace full request lifecycle using correlation ID."""
        return self.cw.get_logs_by_correlation_id(correlation_id)

    def search_errors(self, status_code: int = None, hours_back: int = 1, size: int = 50) -> list[dict]:
        """Search for error logs, optionally filtered by status code."""
        if status_code:
            return self.cw.get_error_logs_by_status(status_code, hours_back)

        query = f"""
            fields @timestamp, api_path, method, status_code, @message
            | filter status_code >= 400
            | sort @timestamp desc
            | limit {size}
        """
        return self.cw.query_logs(query, hours_back)

    def get_top_apis(self, hours_back: int = 1, size: int = 10) -> list[dict]:
        """Get top APIs by request count."""
        return self.cw.get_top_apis(hours_back, size)

    def get_api_history(self, api_path: str, hours_back: int = 24, size: int = 100) -> list[dict]:
        """Get request history for a specific API."""
        return self.cw.get_api_history(api_path, hours_back)
