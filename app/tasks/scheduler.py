"""Background monitoring jobs."""
import structlog
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR
from app.config import get_settings
from app.services.error_analyzer import ErrorAnalyzer
from app.services.performance import PerformanceAnalyzer
from app.services.anomaly_detector import AnomalyDetector
from app.services.sla_tracker import SLATracker
from app.services.incident_analyzer import IncidentAnalyzer
from app.services.cache import CacheService
from app.services.notifier import NotifierService

logger = structlog.get_logger()
scheduler = BackgroundScheduler()


def _on_error(event):
    if event.exception:
        logger.error("job_failed", job_id=event.job_id, error=str(event.exception))


def _get_apis() -> list[str]:
    cache = CacheService()
    apis = cache.get("monitored_apis")
    if apis:
        return apis
    settings = get_settings()
    if settings.monitored_apis:
        api_list = [a.strip() for a in settings.monitored_apis.split(",") if a.strip()]
        cache.set("monitored_apis", api_list, ttl_seconds=86400)
        return api_list
    return []


def monitor_error_rates():
    analyzer = ErrorAnalyzer()
    for api in _get_apis():
        try:
            r = analyzer.analyze_api_errors(api)
            if r["exceeded"]:
                logger.warning("threshold_exceeded", api=api, rate=r["error_rate"])
        except Exception as e:
            logger.error("error_monitor_failed", api=api, error=str(e))


def monitor_slow_apis():
    perf = PerformanceAnalyzer()
    notifier = NotifierService()
    try:
        for api in perf.get_slowest_apis(hours_back=1, limit=5):
            if api.get("exceeds_threshold"):
                notifier.send_teams_alert({
                    "api_path": api.get("path", "unknown"),
                    "alert_type": "slow_api_detected",
                    "threshold": get_settings().slow_api_threshold_ms,
                    "total_requests": int(api.get("request_count", 0)),
                    "timestamp": datetime.utcnow().isoformat(),
                })
    except Exception as e:
        logger.error("slow_monitor_failed", error=str(e))


def run_anomaly_detection():
    detector = AnomalyDetector()
    for api in _get_apis():
        try:
            detector.predict_error_trend(api)
            detector.detect_traffic_anomaly(api)
        except Exception as e:
            logger.error("anomaly_failed", api=api, error=str(e))


def run_recurring_error_check():
    notifier = NotifierService()
    try:
        for err in IncidentAnalyzer().detect_recurring_errors(hours_back=168)[:3]:
            notifier.send_teams_alert({
                "api_path": err.get("api_path", "unknown"), "alert_type": "recurring_error_detected",
                "total_requests": err.get("total_occurrences", 0), "timestamp": err.get("last_seen", ""),
            })
    except Exception as e:
        logger.error("recurring_check_failed", error=str(e))


def run_sla_check():
    sla = SLATracker()
    notifier = NotifierService()
    for api in _get_apis():
        try:
            r = sla.check_sla_compliance(api, hours_back=1)
            if not r["compliant"]:
                notifier.send_teams_alert({
                    "api_path": api, "alert_type": "sla_violation",
                    "error_rate": r["actuals"]["error_rate_pct"],
                    "total_requests": r["actuals"]["total_requests"],
                    "timestamp": datetime.utcnow().isoformat(),
                })
        except Exception as e:
            logger.error("sla_check_failed", api=api, error=str(e))


def hourly_rollup():
    from app.services.dynamodb import DynamoDBService
    db = DynamoDBService()
    cache = CacheService()
    for api in _get_apis():
        try:
            history = db.get_metric_history(api, limit=60)
            if not history:
                continue
            total = sum(int(m.get("total_requests", 0)) for m in history)
            errors = sum(int(m.get("error_count", 0)) for m in history)
            rollup = {"api_path": api, "rollup_type": "hourly", "total_requests": total,
                      "total_errors": errors, "avg_error_rate": (errors / total * 100) if total else 0,
                      "timestamp": datetime.utcnow().isoformat()}
            db.store_metric_snapshot(rollup)
            cache.set(f"rollup:hourly:{api}", rollup, ttl_seconds=7200)
        except Exception as e:
            logger.error("rollup_failed", api=api, error=str(e))


def start_scheduler():
    settings = get_settings()
    scheduler.add_listener(_on_error, EVENT_JOB_ERROR)

    from app.services.deployment_gate import get_deployment_gate

    def recheck_held_deployments():
        get_deployment_gate().recheck_held_deployments()

    jobs = [
        (monitor_error_rates, "interval", {"seconds": settings.monitoring_interval_seconds}, "error_monitor"),
        (monitor_slow_apis, "interval", {"minutes": 5}, "slow_monitor"),
        (run_anomaly_detection, "interval", {"minutes": 5}, "anomaly"),
        (run_recurring_error_check, "interval", {"hours": 1}, "recurring"),
        (run_sla_check, "interval", {"hours": 1}, "sla"),
        (hourly_rollup, "interval", {"hours": 1}, "rollup"),
        (recheck_held_deployments, "interval", {"seconds": 120}, "deployment_gate_recheck"),
    ]
    for func, trigger, kwargs, job_id in jobs:
        scheduler.add_job(func, trigger, **kwargs, id=job_id, replace_existing=True, max_instances=1, coalesce=True)
    scheduler.start()
    logger.info("scheduler_started", jobs=len(scheduler.get_jobs()))


def stop_scheduler():
    scheduler.shutdown(wait=False)
