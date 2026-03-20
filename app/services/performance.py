"""API performance analysis with LLM-powered optimization suggestions."""
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
        cache_key = f"slow_apis:{hours_back}:{limit}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        apis = self.cw.get_slowest_apis(hours_back, limit)
        for api in apis:
            avg = float(api.get("avg_latency", 0))
            api["exceeds_threshold"] = avg > self.settings.slow_api_threshold_ms
            if api["exceeds_threshold"]:
                try:
                    api["suggestion"] = self.llm.invoke(
                        f"Suggest 2-3 optimizations for slow API {api.get('path', '?')} "
                        f"(avg {avg}ms, max {api.get('max_latency', 0)}ms, {api.get('request_count', 0)} reqs). Be concise."
                    )
                except Exception:
                    api["suggestion"] = "Unable to generate suggestion"

        self.cache.set(cache_key, apis, ttl_seconds=300)
        return apis

    def compute_health_score(self, api_path: str, period_minutes: int = 5) -> dict:
        metrics = self.cw.get_api_metrics(api_path, period_minutes=period_minutes)
        latency = self.cw.get_latency_metrics(api_path, period_minutes=period_minutes)

        error_rate = metrics.get("error_rate", 0)
        avg_latency = latency.get("avg_latency_ms", 0)
        total = metrics.get("total_requests", 0)

        e_score = max(0, 100 - error_rate * 2)
        l_score = max(0, 100 - avg_latency / self.settings.slow_api_threshold_ms * 100)
        t_score = min(100, total / 10 * 100) if total else 50

        return {
            "api_path": api_path,
            "score": round(e_score * 0.4 + l_score * 0.35 + t_score * 0.25, 1),
            "error_rate_score": round(e_score, 1),
            "latency_score": round(l_score, 1),
            "throughput_score": round(t_score, 1),
        }
