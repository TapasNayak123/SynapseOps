from fastapi import APIRouter, Query
from app.services.cloudwatch import CloudWatchService
from app.services.log_analyzer import LogAnalyzer
from app.services.performance import PerformanceAnalyzer
from app.services.error_analyzer import ErrorAnalyzer
from app.services.anomaly_detector import AnomalyDetector
from app.services.incident_analyzer import IncidentAnalyzer
from app.services.sla_tracker import SLATracker
from app.services.deployment_tracker import DeploymentTracker

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


# --- Core metrics ---

@router.get("/top-apis")
def get_top_apis(hours_back: int = Query(1, ge=1, le=168)):
    """Get top 10 APIs by usage."""
    return LogAnalyzer().get_top_apis(hours_back=hours_back)


@router.get("/slowest-apis")
def get_slowest_apis(hours_back: int = Query(1, ge=1, le=168)):
    """Get slowest APIs with LLM optimization suggestions."""
    return PerformanceAnalyzer().get_slowest_apis(hours_back=hours_back)


@router.get("/api-history/{api_path:path}")
def get_api_history(api_path: str, hours_back: int = Query(24, ge=1, le=720)):
    """Get request history for a specific API."""
    return LogAnalyzer().get_api_history(api_path, hours_back=hours_back)


@router.get("/health-score/{api_path:path}")
def get_health_score(api_path: str):
    """Get composite health score (0-100) for an API."""
    return PerformanceAnalyzer().compute_health_score(api_path)


# --- Error analysis ---

@router.get("/errors/by-status")
def get_errors_by_status(hours_back: int = Query(1, ge=1, le=168)):
    """Get errors segregated by HTTP status code category (2xx, 4xx, 5xx)."""
    return ErrorAnalyzer().get_errors_by_status(hours_back)


@router.get("/errors/recurring")
def get_recurring_errors(hours_back: int = Query(168, ge=24, le=720)):
    """Detect recurring errors that keep reappearing over multiple days."""
    return IncidentAnalyzer().detect_recurring_errors(hours_back)


@router.get("/correlation/{correlation_id}")
def trace_correlation(correlation_id: str):
    """Trace a request from start to end using correlation ID."""
    return LogAnalyzer().search_by_correlation_id(correlation_id)


# --- Anomaly detection & prediction ---

@router.get("/predict/{api_path:path}")
def predict_error_trend(api_path: str, lookback_minutes: int = Query(30, ge=5, le=120)):
    """Predict if error rate is trending toward threshold breach."""
    return AnomalyDetector().predict_error_trend(api_path, lookback_minutes)


@router.get("/anomaly/{api_path:path}")
def detect_traffic_anomaly(api_path: str, lookback_minutes: int = Query(60, ge=10, le=360)):
    """Detect unusual traffic spikes or drops using z-score analysis."""
    return AnomalyDetector().detect_traffic_anomaly(api_path, lookback_minutes)


# --- Comparative analysis ---

@router.get("/compare/{api_path:path}")
def compare_periods(
    api_path: str,
    period1_hours: int = Query(24, ge=1, le=168),
    period2_hours: int = Query(48, ge=2, le=336),
):
    """Compare API performance between two time periods."""
    return IncidentAnalyzer().compare_periods(api_path, period1_hours, period2_hours)


# --- Incident timeline ---

@router.get("/timeline")
def get_incident_timeline(
    start_hour: int = Query(0, ge=0, le=23),
    end_hour: int = Query(23, ge=0, le=23),
    date: str = Query(None, description="ISO date, e.g. 2026-03-14"),
):
    """Build chronological event log for a time window."""
    return IncidentAnalyzer().build_incident_timeline(start_hour, end_hour, date)


# --- SLA tracking ---

@router.get("/sla/{api_path:path}")
def check_sla(api_path: str, hours_back: int = Query(24, ge=1, le=720)):
    """Check SLA compliance for an API."""
    return SLATracker().check_sla_compliance(api_path, hours_back)


@router.post("/sla/{api_path:path}")
def set_sla_targets(api_path: str, targets: dict):
    """Set custom SLA targets for an API."""
    return SLATracker().set_sla_targets(api_path, targets)


# --- Deployment correlation ---

@router.get("/deployments")
def get_recent_deployments(hours_back: int = Query(24, ge=1, le=168)):
    """Get recent GitHub Actions deployments."""
    return DeploymentTracker().get_recent_deployments(hours_back)


@router.get("/deployments/correlate/{api_path:path}")
def correlate_deployments(api_path: str, hours_back: int = Query(6, ge=1, le=48)):
    """Check if error spikes correlate with recent deployments."""
    return DeploymentTracker().correlate_with_errors(api_path, hours_back)
