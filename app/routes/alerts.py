"""Alerts and auto-fix API endpoints."""
from fastapi import APIRouter, Query
from pydantic import BaseModel, field_validator
from typing import List
from app.services.error_analyzer import ErrorAnalyzer
from app.services.auto_fix import AutoFixService
from app.services.code_analyzer import CodeAnalyzer
from app.services.dynamodb import DynamoDBService
from app.services.cache import CacheService

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class MonitoredApisRequest(BaseModel):
    apis: List[str]

    @field_validator("apis")
    @classmethod
    def validate_apis(cls, v: List[str]) -> List[str]:
        if len(v) > 100:
            raise ValueError("Max 100 APIs")
        return [a.strip() for a in v if a.strip() and len(a) <= 200]


class AutoFixRequest(BaseModel):
    error_message: str
    stack_trace: str = ""

    @field_validator("error_message")
    @classmethod
    def validate_msg(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("error_message required")
        if len(v) > 5000:
            raise ValueError("error_message too long")
        return v


@router.get("/monitored-apis")
def get_monitored_apis():
    return {"monitored_apis": CacheService().get("monitored_apis") or []}


@router.post("/monitored-apis")
def set_monitored_apis(request: MonitoredApisRequest):
    CacheService().set("monitored_apis", request.apis, ttl_seconds=86400 * 30)
    return {"monitored_apis": request.apis, "count": len(request.apis)}


@router.post("/monitored-apis/add/{api_path:path}")
def add_monitored_api(api_path: str):
    cache = CacheService()
    apis = cache.get("monitored_apis") or []
    if api_path not in apis:
        apis.append(api_path)
        cache.set("monitored_apis", apis, ttl_seconds=86400 * 30)
    return {"monitored_apis": apis}


@router.delete("/monitored-apis/remove/{api_path:path}")
def remove_monitored_api(api_path: str):
    cache = CacheService()
    apis = [a for a in (cache.get("monitored_apis") or []) if a != api_path]
    cache.set("monitored_apis", apis, ttl_seconds=86400 * 30)
    return {"monitored_apis": apis}


@router.get("/check/{api_path:path}")
def check_api_errors(api_path: str):
    return ErrorAnalyzer().analyze_api_errors(api_path)


@router.get("/history/{api_path:path}")
def get_alert_history(api_path: str, limit: int = Query(20, ge=1, le=100)):
    return DynamoDBService().get_alerts(api_path, limit=limit)


@router.post("/auto-fix")
def trigger_auto_fix(request: AutoFixRequest):
    return AutoFixService().analyze_and_fix(request.error_message, request.stack_trace)


@router.post("/categorize")
def categorize_error(request: AutoFixRequest):
    analyzer = CodeAnalyzer()
    cat = analyzer.categorize_error(request.error_message, request.stack_trace)
    cat["stack_frames"] = analyzer.parse_stack_trace(request.stack_trace)
    return cat


@router.get("/auto-fix/history")
def get_fix_history(limit: int = Query(20, ge=1, le=100)):
    return AutoFixService().get_fix_history(limit=limit)


@router.get("/audit")
def get_audit_logs(action: str = Query(None), limit: int = Query(50, ge=1, le=200)):
    return DynamoDBService().get_audit_logs(action=action, limit=limit)
