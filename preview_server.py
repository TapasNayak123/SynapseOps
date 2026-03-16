"""Quick preview server to demo the chat UI locally."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
import uvicorn

app = FastAPI()

STATIC_DIR = Path("app/static")


class ChatRequest(BaseModel):
    message: str
    context: dict = None


@app.post("/api/chat/")
def mock_chat(request: ChatRequest):
    """Mock chat endpoint for UI demo."""
    msg = request.message.lower()

    if "correlation" in msg or "trace" in msg:
        # Extract correlation ID from message
        import re
        cid_match = re.search(r'(?:correlation\s*id\s*(?:for\s*)?|trace\s+)(\S+)', msg)
        cid = cid_match.group(1) if cid_match else "unknown"
        return {
            "response": f"Found 2 log entries for correlation ID {cid}. Request started at 05:38:05 on /api/product (GET) and failed at 05:38:06 with 401 AuthenticationError: Invalid token.",
            "data": {"trace": [
                {"timestamp": "2026-03-16T05:38:05.965", "correlationId": cid, "message": "Request started", "method": "GET", "path": "/api/product", "level": "info"},
                {"timestamp": "2026-03-16T05:38:06.012", "correlationId": cid, "message": "Invalid token", "method": "GET", "path": "/api/product", "statusCode": "401", "errorCode": "AUTHENTICATION_ERROR", "level": "error"},
            ]}
        }
    elif "top" in msg and "api" in msg:
        return {
            "response": "Here are your top 10 APIs by request count in the last hour:",
            "data": {"top_apis": [
                {"path": "/api/products", "method": "GET", "request_count": "1247"},
                {"path": "/api/auth/login", "method": "POST", "request_count": "892"},
                {"path": "/api/auth/register", "method": "POST", "request_count": "341"},
                {"path": "/api/products/search", "method": "GET", "request_count": "287"},
                {"path": "/api/orders", "method": "GET", "request_count": "198"},
            ]}
        }
    elif "slow" in msg:
        return {
            "response": "/api/products/search is your slowest API at 1847ms avg latency. This exceeds your 2000ms threshold. Consider adding database indexing on the search fields and implementing response caching.",
            "data": {"slowest_apis": [
                {"path": "/api/products/search", "method": "GET", "avg_latency": "1847", "max_latency": "4200", "request_count": "287"},
                {"path": "/api/orders", "method": "GET", "avg_latency": "923", "max_latency": "2100", "request_count": "198"},
            ]}
        }
    elif "500" in msg or ("error" in msg and "recurring" not in msg):
        return {
            "response": "Found 23 errors with status 500 in the last hour. Most are AuthenticationError on /api/products (15 occurrences) and TypeError on /api/orders (8 occurrences).",
            "data": {"errors": [
                {"timestamp": "2026-03-16T05:32:09", "correlationId": "tapas567abc", "path": "/api/products", "statusCode": "500", "errorCode": "AUTHENTICATION_ERROR", "message": "AuthenticationError: Invalid token"},
                {"timestamp": "2026-03-16T05:31:45", "correlationId": "tapas567def", "path": "/api/orders", "statusCode": "500", "errorCode": "TYPE_ERROR", "message": "TypeError: Cannot read properties of undefined"},
            ]}
        }
    elif "sla" in msg:
        return {
            "response": "/api/products is currently compliant with SLA targets. Error rate is 1.2% (target < 5%), P99 latency is 450ms (target < 1000ms), uptime is 99.8% (target > 99.5%).",
            "data": {"sla": {"api_path": "/api/products", "compliant": True, "actuals": {"error_rate_pct": 1.2, "p99_latency_ms": 450, "uptime_pct": 99.8}}}
        }
    elif "recurring" in msg:
        return {
            "response": "Found 2 recurring errors in the past week. AuthenticationError: Invalid token has appeared 47 times across 5 days. This needs attention.",
            "data": {"recurring": [
                {"fingerprint": "a1b2c3", "api_path": "/api/products", "error_code": "AUTHENTICATION_ERROR", "total_occurrences": 47, "unique_days": 5},
                {"fingerprint": "d4e5f6", "api_path": "/api/orders", "error_code": "VALIDATION_ERROR", "total_occurrences": 12, "unique_days": 3},
            ]}
        }
    elif "deploy" in msg:
        return {
            "response": "Last deployment was 3 hours ago (commit abc1234). No error spike detected after deployment — looks clean.",
            "data": {"deployments": [{"sha": "abc1234", "status": "success", "created_at": "2026-03-16T02:30:00Z"}]}
        }
    elif "health" in msg:
        return {
            "response": "/api/auth/login has a health score of 87.5/100. Error rate score: 95.0, Latency score: 78.2, Throughput score: 82.0. Overall healthy but latency could be improved.",
            "data": {"health": {"api_path": "/api/auth/login", "score": 87.5, "error_rate_score": 95.0, "latency_score": 78.2, "throughput_score": 82.0}}
        }
    elif "happened" in msg or "timeline" in msg:
        return {
            "response": "Between 2pm and 5pm, there were 8 errors and 3 slow requests. Most errors were 401 Unauthorized on /api/products around 3:15pm — likely a token expiry issue.",
            "data": {"timeline": {"total_events": 11, "error_count": 8, "slow_request_count": 3}}
        }
    else:
        return {
            "response": f"I can help you with that! Try asking about top APIs, slowest APIs, errors, SLA compliance, correlation traces, recurring errors, deployments, or health scores. What would you like to know?",
            "data": {}
        }


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/chat")
def chat_ui():
    return FileResponse(str(STATIC_DIR / "chat.html"))


@app.get("/health")
def health():
    return {"status": "healthy", "service": "synapse-ops"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
