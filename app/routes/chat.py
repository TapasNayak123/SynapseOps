"""Chat API endpoint with rate limiting."""
from fastapi import APIRouter, HTTPException
import structlog
from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat_engine import ChatEngine
from app.services.cache import CacheService
from app.config import get_settings

logger = structlog.get_logger()
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
def chat(request: ChatRequest):
    settings = get_settings()
    cache = CacheService()

    if not cache.check_rate_limit("chat:rate:global", settings.chat_rate_limit_per_minute, 60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    msg = (request.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Message required")
    if len(msg) > 2000:
        raise HTTPException(status_code=400, detail="Message too long")

    try:
        result = ChatEngine().process_message(msg, request.context)
        return ChatResponse(
            response=result["response"],
            data=result.get("data"),
            intent=result.get("intent"),
        )
    except Exception as e:
        logger.error("chat_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to process message")
