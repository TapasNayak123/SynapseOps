import structlog
from apscheduler.schedulers.background import BackgroundScheduler
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


def _get_monitored_apis() -> list[str]:
    """Get list of APIs to monitor from cache or config."""
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
    """Per-minute job: check error rates for monitored APIs."""
    analyzer = ErrorAnalyzer()
    apis = _get_monitored_apis()
    if not apis:
        logger.info("no_monitored_apis_configured")
        return

    for api_path in apis:
        try:
            result = analyzer.analyze_api_errors(api_path)
            if result["exceeded"]:
                logger.warning(
                    "error_threshold_exceeded",
                    api_path=api_path,
                    error_rate=result["error_rate"],
                    alerted=result["alerted"],
                )
        except Exception as e:
            logger.error("monitor_error_rates_failed", api_path=api_path, error=str(e))


def monitor_slow_apis():
    """Every 5 minutes: check for slow APIs and notify Teams."""
    perf = PerformanceAnalyzer()
    notifier = NotifierService()
    try:
        slow_apis = perf.get_slowest_apis(hours_back=1, limit=5)
        for api in slow_apis:
            if api.get("exceeds_threshold"):
                logger.warning("slow_api_detected", api=api)
                notifier.send_teams_alert({
                    "api_path": api.get("api_path", "unknown"),
                    "alert_type": "slow_api_detected",
                    "error_rate": 0,
                    "threshold": get_settings().slow_api_threshold_ms,
                    "total_requests": int(api.get("request_count", 0)),
                    "error_count": 0,
                    "timestamp": "",
                })
    except Exception as e:
        logger.error("monitor_slow_apis_failed", error=str(e))


def run_anomaly_detection():
    """Every 5 minutes: predictive alerting + traffic anomaly detection."""
    detector = AnomalyDetector()
    apis = _get_monitored_apis()

    for api_path in apis:
        try:
            # Predictive error trend
            prediction = detector.predict_error_trend(api_path)
            if prediction.get("prediction") == "approaching_threshold":
                logger.warning("error_trend_approaching", api_path=api_path, prediction=prediction)

            # Traffic anomaly
            anomaly = detector.detect_traffic_anomaly(api_path)
            if anomaly.get("anomaly") != "none" and anomaly.get("anomaly") != "insufficient_data":
                logger.warning("traffic_anomaly_detected", api_path=api_path, anomaly=anomaly)
        except Exception as e:
            logger.error("anomaly_detection_failed", api_path=api_path, error=str(e))


def run_recurring_error_check():
    """Hourly: detect recurring errors across the past week."""
    analyzer = IncidentAnalyzer()
    notifier = NotifierService()
    try:
        recurring = analyzer.detect_recurring_errors(hours_back=168)
        if recurring:
            logger.info("recurring_errors_found", count=len(recurring))
            # Notify about top 3 recurring errors
            for err in recurring[:3]:
                notifier.send_teams_alert({
                    "api_path": err.get("api_path", "unknown"),
                    "alert_type": "recurring_error_detected",
                    "error_rate": 0,
                    "threshold": 0,
                    "total_requests": err.get("total_occurrences", 0),
                    "error_count": err.get("total_occurrences", 0),
                    "timestamp": err.get("last_seen", ""),
                })
    except Exception as e:
        logger.error("recurring_error_check_failed", error=str(e))


def run_sla_check():
    """Hourly: check SLA compliance for all monitored APIs."""
    sla = SLATracker()
    notifier = NotifierService()
    apis = _get_monitored_apis()

    for api_path in apis:
        try:
            result = sla.check_sla_compliance(api_path, hours_back=1)
            if not result["compliant"]:
                logger.warning("sla_violation", api_path=api_path, violations=result["violations"])
                notifier.send_teams_alert({
                    "api_path": api_path,
                    "alert_type": "sla_violation",
                    "error_rate": result["actuals"]["error_rate_pct"],
                    "threshold": 0,
                    "total_requests": result["actuals"]["total_requests"],
                    "error_count": 0,
                    "timestamp": "",
                })
        except Exception as e:
            logger.error("sla_check_failed", api_path=api_path, error=str(e))


def hourly_rollup():
    """Hourly: aggregate metrics and store rollup in DynamoDB."""
    from app.services.dynamodb import DynamoDBService
    from datetime import datetime

    db = DynamoDBService()
    cache = CacheService()
    apis = _get_monitored_apis()

    for api_path in apis:
        try:
            history = db.get_metric_history(api_path, limit=60)
            if not history:
                continue

            total_requests = sum(int(m.get("total_requests", 0)) for m in history)
            total_errors = sum(int(m.get("error_count", 0)) for m in history)
            avg_error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0

            rollup = {
                "api_path": api_path,
                "rollup_type": "hourly",
                "total_requests": total_requests,
                "total_errors": total_errors,
                "avg_error_rate": avg_error_rate,
                "datapoints": len(history),
                "timestamp": datetime.utcnow().isoformat(),
            }
            db.store_metric_snapshot(rollup)
            cache.set(f"rollup:hourly:{api_path}", rollup, ttl_seconds=7200)
            logger.info("hourly_rollup_complete", api_path=api_path, requests=total_requests)
        except Exception as e:
            logger.error("hourly_rollup_failed", api_path=api_path, error=str(e))


def start_scheduler():
    """Initialize and start all background monitoring jobs."""
    settings = get_settings()

    # Per-minute: error rate monitoring
    scheduler.add_job(
        monitor_error_rates, "interval",
        seconds=settings.monitoring_interval_seconds,
        id="error_rate_monitor", replace_existing=True,
    )

    # Every 5 min: slow API detection
    scheduler.add_job(
        monitor_slow_apis, "interval",
        minutes=5, id="slow_api_monitor", replace_existing=True,
    )

    # Every 5 min: anomaly detection + predictive alerting
    scheduler.add_job(
        run_anomaly_detection, "interval",
        minutes=5, id="anomaly_detector", replace_existing=True,
    )

    # Hourly: recurring error check
    scheduler.add_job(
        run_recurring_error_check, "interval",
        hours=1, id="recurring_error_check", replace_existing=True,
    )

    # Hourly: SLA compliance check
    scheduler.add_job(
        run_sla_check, "interval",
        hours=1, id="sla_check", replace_existing=True,
    )

    # Hourly: metric rollup aggregation
    scheduler.add_job(
        hourly_rollup, "interval",
        hours=1, id="hourly_rollup", replace_existing=True,
    )

    scheduler.start()
    logger.info("scheduler_started", jobs=len(scheduler.get_jobs()))


def stop_scheduler():
    """Gracefully stop the scheduler."""
    scheduler.shutdown(wait=False)
    logger.info("scheduler_stopped")
