"""Log analysis using CloudWatch Logs Insights."""
from app.services.cloudwatch import CloudWatchService, F_PATH, F_METHOD, F_STATUS, F_MESSAGE, F_ERROR_CODE, F_LEVEL


class LogAnalyzer:
    def __init__(self):
        self.cw = CloudWatchService()

    def search_by_correlation_id(self, correlation_id: str, hours_back: float = 24) -> list[dict]:
        return self.cw.get_logs_by_correlation_id(correlation_id, hours_back)

    def search_errors(self, status_code: int = None, hours_back: int = 1, size: int = 50) -> list[dict]:
        if status_code:
            return self.cw.get_error_logs_by_status(status_code, hours_back)
        # Use get_error_logs which has stream-scan fallback built in
        return self.cw.get_error_logs(hours_back)[:size]

    def get_top_apis(self, hours_back: int = 1, size: int = 10) -> list[dict]:
        return self.cw.get_top_apis(hours_back, size)

    def get_api_history(self, api_path: str, hours_back: int = 24, size: int = 100) -> list[dict]:
        return self.cw.get_api_history(api_path, hours_back)
