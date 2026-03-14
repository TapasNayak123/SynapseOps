from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


class HttpStatusCategory(str, Enum):
    SUCCESS_2XX = "2xx"
    REDIRECT_3XX = "3xx"
    CLIENT_ERROR_4XX = "4xx"
    SERVER_ERROR_5XX = "5xx"


class ApiMetric(BaseModel):
    api_path: str
    method: str
    total_requests: int = 0
    error_count: int = 0
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    timestamp: datetime = datetime.utcnow()


class ErrorGroup(BaseModel):
    api_path: str
    status_code: int
    status_category: HttpStatusCategory
    error_message: str
    fingerprint: str
    count: int = 0
    first_seen: datetime = datetime.utcnow()
    last_seen: datetime = datetime.utcnow()


class AlertEvent(BaseModel):
    api_path: str
    alert_type: str
    message: str
    error_rate: float = 0.0
    threshold: float = 0.0
    timestamp: datetime = datetime.utcnow()
    notified: bool = False


class SlowApiReport(BaseModel):
    api_path: str
    method: str
    avg_latency_ms: float
    p99_latency_ms: float
    sample_count: int
    suggestion: Optional[str] = None


class CorrelationTrace(BaseModel):
    correlation_id: str
    api_path: str
    method: str
    status_code: int
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    logs: list[dict] = []


class ChatRequest(BaseModel):
    message: str
    context: Optional[dict] = None


class ChatResponse(BaseModel):
    response: str
    data: Optional[dict] = None


class CodeFixResult(BaseModel):
    error_message: str
    file_path: Optional[str] = None
    original_code: Optional[str] = None
    fixed_code: Optional[str] = None
    explanation: str
    confidence: float = 0.0
    applied: bool = False


class HealthScore(BaseModel):
    api_path: str
    score: float  # 0-100
    error_rate_score: float
    latency_score: float
    throughput_score: float
    timestamp: datetime = datetime.utcnow()


class PredictionResult(BaseModel):
    api_path: str
    current_error_rate: float
    slope_per_minute: float
    trend: str  # increasing, decreasing, stable
    prediction: str  # approaching_threshold, already_exceeded, safe, insufficient_data
    predicted_breach_in_minutes: Optional[float] = None
    severity: Optional[str] = None


class TrafficAnomaly(BaseModel):
    api_path: str
    current_requests: int
    baseline_mean: float
    baseline_std_dev: float
    z_score: float
    anomaly: str  # none, traffic_spike, traffic_drop
    severity: Optional[str] = None


class SLAResult(BaseModel):
    api_path: str
    period_hours: int
    compliant: bool
    targets: dict
    actuals: dict
    violations: list[dict]


class DeploymentCorrelation(BaseModel):
    api_path: str
    recent_deployments: int
    correlations_found: int
    correlations: list[dict]


class RecurringError(BaseModel):
    fingerprint: str
    api_path: str
    status_code: str
    sample_message: str
    total_occurrences: int
    unique_days: int
    recurring: bool
    first_seen: str
    last_seen: str


class IncidentTimeline(BaseModel):
    time_window: dict
    total_events: int
    error_count: int
    slow_request_count: int
    timeline: list[dict]
