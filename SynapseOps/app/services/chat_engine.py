"""
Smart chat engine that interprets user intent and queries the right data sources.
Supports natural language time ranges, comparative queries, and data-driven answers.
"""
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
        """
        Interpret user message, determine intent, fetch relevant data,
        and generate a contextual response.
        """
        intent = self._classify_intent(message)
        data = self._fetch_data_for_intent(intent, message)

        if extra_context:
            data.update(extra_context)

        # Generate response with full context
        response = self.llm.chat(message, data)

        return {
            "response": response,
            "intent": intent,
            "data": data,
        }

    def _classify_intent(self, message: str) -> dict:
        """Use LLM to classify the user's intent into actionable categories."""
        prompt = f"""Classify this monitoring query into one of these intents.
Return ONLY valid JSON, no other text.

Intents:
- top_apis: user wants to see most used APIs
- slowest_apis: user wants to see slow APIs
- api_history: user wants history of a specific API (extract api_path)
- correlation_trace: user wants to trace a request (extract correlation_id)
- error_analysis: user wants to see errors (extract status_code if mentioned)
- compare: user wants to compare periods (extract api_path, periods)
- incident_timeline: user wants to know what happened in a time range (extract start_hour, end_hour)
- health_check: user wants health score of an API (extract api_path)
- sla_check: user wants SLA compliance (extract api_path)
- deployment_check: user wants to see recent deployments or correlate with errors
- anomaly_check: user wants anomaly/prediction info (extract api_path)
- recurring_errors: user wants to see recurring/repeated errors
- general: general question about the service

User message: "{message}"

JSON format: {{"intent": "...", "api_path": "...", "correlation_id": "...", "status_code": null, "start_hour": null, "end_hour": null, "hours_back": 1}}"""

        try:
            result = self.llm.invoke(prompt, max_tokens=256)
            return json.loads(result)
        except (json.JSONDecodeError, Exception):
            return {"intent": "general"}

    def _fetch_data_for_intent(self, intent: dict, message: str) -> dict:
        """Fetch the right data based on classified intent."""
        intent_type = intent.get("intent", "general")
        api_path = intent.get("api_path", "")
        hours_back = int(intent.get("hours_back", 1) or 1)

        try:
            if intent_type == "top_apis":
                return {"top_apis": self.logs.get_top_apis(hours_back=hours_back)}

            elif intent_type == "slowest_apis":
                return {"slowest_apis": self.perf.get_slowest_apis(hours_back=hours_back)}

            elif intent_type == "api_history" and api_path:
                return {"api_history": self.logs.get_api_history(api_path, hours_back=hours_back)}

            elif intent_type == "correlation_trace":
                cid = intent.get("correlation_id", "")
                if cid:
                    return {"trace": self.logs.search_by_correlation_id(cid)}
                return {"error": "No correlation ID provided"}

            elif intent_type == "error_analysis":
                status = intent.get("status_code")
                if status:
                    return {"errors": self.logs.search_errors(status_code=int(status), hours_back=hours_back)}
                return {"errors_by_status": self.errors.get_errors_by_status(hours_back)}

            elif intent_type == "compare" and api_path:
                return {"comparison": self.incidents.compare_periods(api_path)}

            elif intent_type == "incident_timeline":
                start = int(intent.get("start_hour", 0) or 0)
                end = int(intent.get("end_hour", 23) or 23)
                return {"timeline": self.incidents.build_incident_timeline(start, end)}

            elif intent_type == "health_check" and api_path:
                return {"health": self.perf.compute_health_score(api_path)}

            elif intent_type == "sla_check" and api_path:
                return {"sla": self.sla.check_sla_compliance(api_path)}

            elif intent_type == "deployment_check":
                data = {"deployments": self.deployments.get_recent_deployments()}
                if api_path:
                    data["correlation"] = self.deployments.correlate_with_errors(api_path)
                return data

            elif intent_type == "anomaly_check" and api_path:
                return {
                    "prediction": self.anomaly.predict_error_trend(api_path),
                    "traffic_anomaly": self.anomaly.detect_traffic_anomaly(api_path),
                }

            elif intent_type == "recurring_errors":
                return {"recurring": self.incidents.detect_recurring_errors()}

            else:
                # General: provide a summary
                return {
                    "top_apis": self.logs.get_top_apis(hours_back=1, size=5),
                    "slowest_apis": self.cw.get_slowest_apis(hours_back=1, limit=5),
                }

        except Exception as e:
            logger.error("chat_data_fetch_failed", intent=intent_type, error=str(e))
            return {"error": f"Failed to fetch data: {str(e)}"}
