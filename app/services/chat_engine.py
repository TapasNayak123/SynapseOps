"""Smart chat engine with intent classification and data-driven responses."""
import json
import structlog
from app.config import get_settings
from app.services.llm import LLMService
from app.services.cloudwatch import CloudWatchService
from app.services.log_analyzer import LogAnalyzer
from app.services.performance import PerformanceAnalyzer
from app.services.error_analyzer import ErrorAnalyzer
from app.services.incident_analyzer import IncidentAnalyzer
from app.services.anomaly_detector import AnomalyDetector
from app.services.sla_tracker import SLATracker
from app.services.deployment_tracker import DeploymentTracker
from app.services.k8s_client import K8sClient

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
        self.k8s = K8sClient()

    @staticmethod
    def _get_service_info() -> dict:
        """Build a context dict describing the monitored service and SynapseOps itself."""
        s = get_settings()
        monitored = [a.strip() for a in s.monitored_apis.split(",") if a.strip()] if s.monitored_apis else []
        repos = s.github_repos_list
        return {
            "platform": "SynapseOps",
            "description": (
                "SynapseOps is an AI-powered DevOps monitoring and observability platform. "
                "It monitors a target application's APIs in real time via CloudWatch logs, "
                "provides health scores, error analysis, latency tracking, anomaly detection, "
                "SLA compliance checks, deployment correlation, and automated PR code reviews. "
                "It uses Amazon Bedrock LLMs for intelligent analysis and chat."
            ),
            "monitored_service": {
                "cloudwatch_log_group": s.cloudwatch_log_group,
                "monitored_apis": monitored,
                "github_repos": repos,
            },
            "capabilities": [
                "Top API usage tracking",
                "Error analysis (4xx/5xx) with breakdown by status code",
                "Slowest API latency analysis",
                "Recurring error detection",
                "Request tracing by correlation ID",
                "API health scoring (0-100)",
                "Period-over-period comparison",
                "SLA compliance checking",
                "Deployment tracking and error correlation",
                "Anomaly detection (traffic and error trends)",
                "Automated GitHub PR review with multi-agent analysis",
            ],
            "infrastructure": {
                "llm_model": s.bedrock_model_id,
                "region": s.aws_region,
                "storage": "DynamoDB",
                "cache": "Redis (optional)",
            },
        }

    @staticmethod
    def _is_empty_result(data: dict) -> bool:
        """Check if fetched data contains no meaningful results."""
        if not data or data.get("error"):
            return True
        # service_info and infra data always has content
        if "platform" in data or "service_info" in data:
            return False
        if "pod_status" in data or "deployment_gate" in data:
            return False
        for key, val in data.items():
            if key in ("hours_back",):
                continue
            if isinstance(val, list) and len(val) > 0:
                return False
            if isinstance(val, dict):
                # Check nested dicts like errors_by_status, comparison, health, sla
                if any(v for v in val.values() if v not in (0, 0.0, "", None, [], {})):
                    return False
            if isinstance(val, (int, float)) and val > 0:
                return False
        return True

    @staticmethod
    def _format_time_range(hours: float) -> str:
        """Human-readable time range label."""
        if hours < 1:
            return f"{round(hours * 60)} minutes"
        if hours < 24:
            h = round(hours)
            return f"{h} hour{'s' if h != 1 else ''}"
        days = round(hours / 24)
        if days < 30:
            return f"{days} day{'s' if days != 1 else ''}"
        months = round(hours / 720)
        if months < 12:
            return f"{months} month{'s' if months != 1 else ''}"
        years = round(hours / 8760)
        return f"{years} year{'s' if years != 1 else ''}"

    def process_message(self, message: str, extra_context: dict = None) -> dict:
        last_intent = ""
        if extra_context:
            last_intent = extra_context.get("last_intent", "")
        intent = self._classify_intent(message, last_intent=last_intent)
        # Use hours_back from UI time range selector if provided
        hours_override = None
        if extra_context and "hours_back" in extra_context:
            hours_override = extra_context.get("hours_back")
        data = self._fetch_data(intent, hours_override=hours_override)

        # Check for empty results before calling LLM
        hours_used = hours_override if hours_override is not None else int(intent.get("hours_back", 1) or 1)
        if self._is_empty_result(data):
            time_label = self._format_time_range(hours_used)
            no_data_msg = f"No data found for the selected time range ({time_label}). Try expanding the range or check if the APIs have traffic in this period."
            return {"response": no_data_msg, "intent": intent, "data": None}

        if extra_context:
            data.update(extra_context)

        response = self.llm.chat(message, data)

        # Hide raw JSON for service_info — it's metadata, not useful to display
        t = intent.get("intent", "general")
        show_data = None if t == "service_info" else data

        return {"response": response, "intent": intent, "data": show_data}

    def _classify_intent(self, message: str, last_intent: str = "") -> dict:
        # Sanitize user message to prevent prompt injection
        sanitized = message.replace('"', '\\"').replace('\n', ' ').replace('\r', '')[:500]
        follow_up_hint = ""
        if last_intent:
            follow_up_hint = f'\nPrevious intent was: "{last_intent}". If the user\'s message is a short follow-up (e.g., "check for X", "what about Y", "now for Z"), reuse the same intent with the new parameters extracted from the message.'
        prompt = f"""Classify this monitoring query. Return ONLY valid JSON.
Intents: top_apis, slowest_apis, api_history, correlation_trace, error_analysis, compare, incident_timeline, health_check, sla_check, deployment_check, anomaly_check, recurring_errors, pod_status, pipeline_status, pr_summary, deployment_gate_status, service_info, general
Intent guide:
- "pod_status": pod health, restarts, CPU/memory usage, node status, kubernetes resources
- "pipeline_status": CI/CD pipeline runs, GitHub Actions, build status, workflow failures
- "pr_summary": pull request reviews, PR analysis, code reviews, recent PRs
- "deployment_gate_status": deployment gate, held deployments, deploy safety, traffic conditions
- "service_info": what is this platform, capabilities, what service is monitored
Use the most specific intent that matches.{follow_up_hint}
User: "{sanitized}"
JSON: {{"intent": "...", "api_path": "...", "correlation_id": "...", "status_code": null, "start_hour": null, "end_hour": null, "hours_back": 1}}"""
        try:
            text = self.llm.invoke(prompt, max_tokens=256).strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0].strip()
            return json.loads(text)
        except Exception:
            return {"intent": "general"}

    def _fetch_data(self, intent: dict, hours_override: float = None) -> dict:
        t = intent.get("intent", "general")
        api = intent.get("api_path", "")
        hours = hours_override if hours_override is not None else int(intent.get("hours_back", 1) or 1)
        # Ensure hours is at least a small positive value
        hours = max(hours, 0.01)

        try:
            if t == "service_info":
                info = self._get_service_info()
                # Also include a quick usage summary so the LLM can mention real numbers
                try:
                    info["usage_summary"] = {
                        "top_apis": self.logs.get_top_apis(hours_back=hours, size=5),
                        "total_errors": self.errors.get_errors_by_status(hours),
                    }
                except Exception:
                    pass
                return info
            if t == "top_apis":
                return {"top_apis": self.logs.get_top_apis(hours_back=hours)}
            if t == "slowest_apis":
                return {"slowest_apis": self.perf.get_slowest_apis(hours_back=hours)}
            if t == "api_history" and api:
                return {"api_history": self.logs.get_api_history(api, hours_back=hours)}
            if t == "correlation_trace":
                cid = intent.get("correlation_id", "")
                return {"trace": self.logs.search_by_correlation_id(cid, hours_back=hours)} if cid else {"error": "No correlation ID"}
            if t == "error_analysis":
                sc = intent.get("status_code")
                if sc:
                    return {"errors": self.logs.search_errors(status_code=int(sc), hours_back=hours)}
                # No specific status code — return both breakdown and recent error logs
                return {
                    "errors_by_status": self.errors.get_errors_by_status(hours),
                    "recent_errors": self.logs.search_errors(hours_back=hours, size=30),
                }
            if t == "compare" and api:
                return {"comparison": self.incidents.compare_periods(api, p1_hours=hours, p2_hours=hours * 2)}
            if t == "incident_timeline":
                return {"timeline": self.incidents.build_incident_timeline(int(intent.get("start_hour", 0) or 0), int(intent.get("end_hour", 23) or 23))}
            if t == "health_check" and api:
                return {"health": self.perf.compute_health_score(api, period_minutes=max(int(hours * 60), 5))}
            if t == "sla_check" and api:
                return {"sla": self.sla.check_sla_compliance(api, hours_back=max(int(hours), 1))}
            if t == "deployment_check":
                data = {"deployments": self.deployments.get_recent_deployments(hours_back=max(int(hours), 1))}
                if api:
                    data["correlation"] = self.deployments.correlate_with_errors(api, hours_back=max(int(hours), 1))
                return data
            if t == "anomaly_check" and api:
                mins = max(int(hours * 60), 5)
                return {"prediction": self.anomaly.predict_error_trend(api, lookback_minutes=mins), "traffic_anomaly": self.anomaly.detect_traffic_anomaly(api, lookback_minutes=mins)}
            if t == "recurring_errors":
                return {"recurring": self.incidents.detect_recurring_errors(hours_back=max(int(hours), 1))}
            if t == "pod_status":
                return self._fetch_pod_status()
            if t == "pipeline_status":
                return self._fetch_pipeline_status(hours)
            if t == "pr_summary":
                return self._fetch_pr_summary()
            if t == "deployment_gate_status":
                return self._fetch_gate_status()
            # General fallback — include service info + quick data summary
            data = {
                "service_info": self._get_service_info(),
                "top_apis": self.logs.get_top_apis(hours_back=hours, size=5),
                "slowest_apis": self.cw.get_slowest_apis(hours_back=hours, limit=5),
            }
            return data
        except Exception as e:
            logger.error("fetch_failed", intent=t, error=str(e))
            return {"error": str(e)}

    # ── New data fetchers for expanded intents ────────────────────────────

    def _fetch_pod_status(self) -> dict:
        """Fetch Kubernetes pod status, resource usage, and node info."""
        try:
            summary = self.k8s.get_all_pods_summary()
            if summary.get("total_pods", 0) > 0:
                return {"pod_status": summary}
            return {"pod_status": "kubectl not available or no pods found"}
        except Exception as e:
            logger.warning("k8s_fetch_failed", error=str(e))
            return {"pod_status": "Kubernetes data unavailable"}

    def _fetch_pipeline_status(self, hours: float) -> dict:
        """Fetch recent GitHub Actions pipeline runs."""
        from store import pipeline_store
        try:
            # Get from deployment tracker (live GitHub API)
            runs = self.deployments.get_recent_deployments(hours_back=max(int(hours), 1))
            # Also get analyzed failures from DynamoDB
            failures = pipeline_store.all()[:10]
            failure_list = []
            for f in failures:
                failure_list.append({
                    "repo": f.repo, "run_id": f.run_id, "workflow": f.workflow,
                    "branch": f.branch, "status": f.status,
                    "failed_jobs": f.failed_jobs[:3],
                    "analysis_snippet": (f.analysis or "")[:300],
                    "autoheal_status": f.autoheal_status,
                    "autoheal_pr": f.autoheal_pr,
                })
            return {
                "recent_pipeline_runs": runs,
                "analyzed_failures": failure_list,
                "total_runs": len(runs),
                "failed_count": sum(1 for r in runs if r.get("status") == "failure"),
                "success_count": sum(1 for r in runs if r.get("status") == "success"),
            }
        except Exception as e:
            logger.warning("pipeline_fetch_failed", error=str(e))
            return {"error": f"Pipeline data unavailable: {e}"}

    def _fetch_pr_summary(self) -> dict:
        """Fetch recent PR reviews and analysis."""
        from store import pr_store
        try:
            records = pr_store.all()[:10]
            prs = []
            for r in records:
                prs.append({
                    "repo": r.repo, "pr_number": r.pr_number, "title": r.title,
                    "author": r.author, "branch": r.branch, "target": r.target,
                    "risk_level": r.risk_level, "pr_type": r.pr_type,
                    "priority": r.priority, "summary_snippet": (r.summary or "")[:200],
                    "files_changed": r.files_changed,
                    "additions": r.additions, "deletions": r.deletions,
                })
            stats = pr_store.stats()
            return {
                "recent_prs": prs,
                "stats": {
                    "total_reviewed": stats.get("total", 0),
                    "avg_duration_seconds": stats.get("avg_duration", 0),
                    "risk_distribution": stats.get("risk_counts", {}),
                    "type_distribution": stats.get("type_counts", {}),
                },
            }
        except Exception as e:
            logger.warning("pr_fetch_failed", error=str(e))
            return {"error": f"PR data unavailable: {e}"}

    def _fetch_gate_status(self) -> dict:
        """Fetch deployment gate status and held deployments."""
        try:
            from app.services.deployment_gate import get_deployment_gate
            gate = get_deployment_gate()
            held = gate.get_held_deployments()
            pending = [h for h in held if not h.get("released")]
            released = [h for h in held if h.get("released")]
            return {
                "deployment_gate": {
                    "total_held": len(held),
                    "currently_held": len(pending),
                    "released": len(released),
                    "pending_deployments": pending[:5],
                    "recently_released": released[:5],
                }
            }
        except Exception as e:
            logger.warning("gate_fetch_failed", error=str(e))
            return {"error": f"Deployment gate data unavailable: {e}"}
