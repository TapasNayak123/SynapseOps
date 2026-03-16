"""Smart chat engine with intent classification and data-driven responses."""
import json
import structlog
from app.services.llm import LLMService
from app.services.cloudwatch import CloudWatchService
from app.services.log_analyzer import LogAnalyzer
from app.services.performance import PerformanceAnalyzer
from app.services.error_analyzer import ErrorAnalyzer
from app.services.incident_analyzer import IncidentAnalyzer
from app.services.anomaly_detector import AnomalyDetector
from app.services.sla_tracker import SLATracker
from app.services.deployment_tracker import DeploymentTracker

logger = structlog.get_logger()


class ChatEngine:
    def __init__(self):
        self.llm = LLMService()
        self.cw = CloudWatchService()
        self.logs = LogAnalyzer()
        self.perf = PerformanceAnalyzer()
        self.errors = ErrorAnalyzer()
        self.incidents = IncidentAnalyzer()
        self.anomaly = AnomalyDetector()
        self.sla = SLATracker()
        self.deployments = DeploymentTracker()

    def process_message(self, message: str, extra_context: dict = None) -> dict:
        intent = self._classify_intent(message)
        data = self._fetch_data(intent)
        if extra_context:
            data.update(extra_context)
        return {"response": self.llm.chat(message, data), "intent": intent, "data": data}

    def _classify_intent(self, message: str) -> dict:
        # Sanitize user message to prevent prompt injection
        sanitized = message.replace('"', '\\"').replace('\n', ' ').replace('\r', '')[:500]
        prompt = f"""Classify this monitoring query. Return ONLY valid JSON.
Intents: top_apis, slowest_apis, api_history, correlation_trace, error_analysis, compare, incident_timeline, health_check, sla_check, deployment_check, anomaly_check, recurring_errors, general
User: "{sanitized}"
JSON: {{"intent": "...", "api_path": "...", "correlation_id": "...", "status_code": null, "start_hour": null, "end_hour": null, "hours_back": 1}}"""
        try:
            return json.loads(self.llm.invoke(prompt, max_tokens=256))
        except Exception:
            return {"intent": "general"}

    def _fetch_data(self, intent: dict) -> dict:
        t = intent.get("intent", "general")
        api = intent.get("api_path", "")
        hours = int(intent.get("hours_back", 1) or 1)

        try:
            if t == "top_apis":
                return {"top_apis": self.logs.get_top_apis(hours_back=hours)}
            if t == "slowest_apis":
                return {"slowest_apis": self.perf.get_slowest_apis(hours_back=hours)}
            if t == "api_history" and api:
                return {"api_history": self.logs.get_api_history(api, hours_back=hours)}
            if t == "correlation_trace":
                cid = intent.get("correlation_id", "")
                return {"trace": self.logs.search_by_correlation_id(cid)} if cid else {"error": "No correlation ID"}
            if t == "error_analysis":
                sc = intent.get("status_code")
                return {"errors": self.logs.search_errors(status_code=int(sc), hours_back=hours)} if sc else {"errors_by_status": self.errors.get_errors_by_status(hours)}
            if t == "compare" and api:
                return {"comparison": self.incidents.compare_periods(api)}
            if t == "incident_timeline":
                return {"timeline": self.incidents.build_incident_timeline(int(intent.get("start_hour", 0) or 0), int(intent.get("end_hour", 23) or 23))}
            if t == "health_check" and api:
                return {"health": self.perf.compute_health_score(api)}
            if t == "sla_check" and api:
                return {"sla": self.sla.check_sla_compliance(api)}
            if t == "deployment_check":
                data = {"deployments": self.deployments.get_recent_deployments()}
                if api:
                    data["correlation"] = self.deployments.correlate_with_errors(api)
                return data
            if t == "anomaly_check" and api:
                return {"prediction": self.anomaly.predict_error_trend(api), "traffic_anomaly": self.anomaly.detect_traffic_anomaly(api)}
            if t == "recurring_errors":
                return {"recurring": self.incidents.detect_recurring_errors()}
            return {"top_apis": self.logs.get_top_apis(hours_back=1, size=5), "slowest_apis": self.cw.get_slowest_apis(hours_back=1, limit=5)}
        except Exception as e:
            logger.error("fetch_failed", intent=t, error=str(e))
            return {"error": str(e)}
