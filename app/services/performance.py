import structlog
from app.config import get_settings
from app.services.cloudwatch import CloudWatchService
from app.services.cache import CacheService
from app.services.llm import LLMService

logger = structlog.get_logger()


class PerformanceAnalyzer:
    def __init__(self):
        self.cw = CloudWatchService()
        self.cache = CacheService()
        self.llm = LLMService()
        self.settings = get_settings()

    def get_slowest_apis(self, hours_back: int = 1, limit: int = 10) -> list[dict]:
        """Get slowest APIs with optimization suggestions."""
        cache_key = f"slow_apis:{hours_back}:{limit}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        slow_apis = self.cw.get_slowest_apis(hours_back, limit)

        for api in slow_apis:
            avg = float(api.get("avg_latency", 0))
            if avg > self.settings.slow_api_threshold_ms:
                api["exceeds_threshold"] = True
                api["suggestion"] = self._get_optimization_suggestion(api)
            else:
                api["exceeds_threshold"] = False

        self.cache.set(cache_key, slow_apis, ttl_seconds=300)
        return slow_apis

    def _get_optimization_suggestion(self, api_data: dict) -> str:
        """Use LLM to suggest optimizations for slow APIs."""
        prompt = f"""Analyze this slow API and suggest optimizations:
- API: {api_data.get('api_path', 'unknown')} ({api_data.get('method', 'GET')})
- Average latency: {api_data.get('avg_latency', 0)}ms
- Max latency: {api_data.get('max_latency', 0)}ms
- Request count: {api_data.get('request_count', 0)}

Provide 2-3 concise, actionable suggestions."""
        try:
            return self.llm.invoke(prompt)
        except Exception as e:
            logger.error("llm_suggestion_failed", error=str(e))
            return "Unable to generate suggestion"

    def compute_health_score(self, api_path: str) -> dict:
        """Compute a 0-100 health score for an API."""
        metrics = self.cw.get_api_metrics(api_path, period_minutes=5)
        latency = self.cw.get_latency_metrics(api_path, period_minutes=5)

        error_rate = metrics.get("error_rate", 0)
        avg_latency = latency.get("avg_latency_ms", 0)
        total_requests = metrics.get("total_requests", 0)

        error_score = max(0, 100 - (error_rate * 2))
        latency_score = max(0, 100 - (avg_latency / self.settings.slow_api_threshold_ms * 100))
        throughput_score = min(100, total_requests / 10 * 100) if total_requests > 0 else 50

        overall = (error_score * 0.4) + (latency_score * 0.35) + (throughput_score * 0.25)

        return {
            "api_path": api_path,
            "score": round(overall, 1),
            "error_rate_score": round(error_score, 1),
            "latency_score": round(latency_score, 1),
            "throughput_score": round(throughput_score, 1),
        }
