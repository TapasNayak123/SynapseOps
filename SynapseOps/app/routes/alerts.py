from fastapi import APIRouter, Query
from pydantic import BaseModel
from app.services.error_analyzer import ErrorAnalyzer
from app.services.auto_fix import AutoFixService
from app.services.code_analyzer import CodeAnalyzer
from app.services.dynamodb import DynamoDBService
from app.services.cache import CacheService

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

analyzer = ErrorAnalyzer()
auto_fix = AutoFixService()
code_analyzer = CodeAnalyzer()
db = DynamoDBService()
cache = CacheService()


# --- Monitoring management ---

class MonitoredApisRequest(BaseModel):
    apis: list[str]


@router.get("/monitored-apis")
def get_monitored_apis():
    """Get list of currently monitored APIs."""
    apis = cache.get("monitored_apis")
    return {"monitored_apis": apis or []}


@router.post("/monitored-apis")
def set_monitored_apis(request: MonitoredApisRequest):
    """Set the list of APIs to monitor."""
    cache.set("monitored_apis", request.apis, ttl_seconds=86400 * 30)
    return {"monitored_apis": request.apis, "count": len(request.apis)}


@router.post("/monitored-apis/add/{api_path:path}")
def add_monitored_api(api_path: str):
    """Add a single API to the monitoring list."""
    apis = cache.get("monitored_apis") or []
    if api_path not in apis:
        apis.append(api_path)
        cache.set("monitored_apis", apis, ttl_seconds=86400 * 30)
    return {"monitored_apis": apis}


@router.delete("/monitored-apis/remove/{api_path:path}")
def remove_monitored_api(api_path: str):
    """Remove a single API from the monitoring list."""
    apis = cache.get("monitored_apis") or []
    apis = [a for a in apis if a != api_path]
    cache.set("monitored_apis", apis, ttl_seconds=86400 * 30)
    return {"monitored_apis": apis}


# --- Error analysis & alerting ---

@router.get("/check/{api_path:path}")
def check_api_errors(api_path: str):
    """Manually trigger error analysis for an API."""
    return analyzer.analyze_api_errors(api_path)


@router.get("/history/{api_path:path}")
def get_alert_history(api_path: str, limit: int = Query(20, ge=1, le=100)):
    """Get alert history for an API."""
    return db.get_alerts(api_path, limit=limit)


# --- Auto-fix ---

class AutoFixRequest(BaseModel):
    error_message: str
    stack_trace: str = ""


@router.post("/auto-fix")
def trigger_auto_fix(request: AutoFixRequest):
    """
    Full auto-fix pipeline:
    1. Categorize bug (rule-based pattern matching)
    2. Parse stack trace → extract file path + line number
    3. Fetch actual source code from GitHub
    4. Send code + error to Bedrock LLM for fix generation
    5. Create PR if auto-fixable + confidence >= 0.8
    """
    return auto_fix.analyze_and_fix(request.error_message, request.stack_trace)


class CategorizeRequest(BaseModel):
    error_message: str
    stack_trace: str = ""


@router.post("/categorize")
def categorize_error(request: CategorizeRequest):
    """
    Categorize a bug without attempting a fix.
    Returns category, severity, and whether it's auto-fixable.

    Auto-fixable categories:
    - null_reference, type_error, missing_import, unhandled_promise,
      missing_null_check, syntax_error, env_config, missing_await,
      wrong_status_code, missing_validation

    Needs human review:
    - memory_leak, race_condition, db_connection, auth_failure,
      timeout, infrastructure, unknown
    """
    category = code_analyzer.categorize_error(request.error_message, request.stack_trace)
    frames = code_analyzer.parse_stack_trace(request.stack_trace)
    category["stack_frames"] = frames
    return category


@router.get("/auto-fix/history")
def get_fix_history(limit: int = Query(20, ge=1, le=100)):
    """Get auto-fix attempt history."""
    return auto_fix.get_fix_history(limit=limit)


# --- Audit trail ---

@router.get("/audit")
def get_audit_logs(action: str = Query(None), limit: int = Query(50, ge=1, le=200)):
    """Get audit logs (all agent actions are tracked)."""
    return db.get_audit_logs(action=action, limit=limit)
