from fastapi import APIRouter
from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat_engine import ChatEngine

router = APIRouter(prefix="/api/chat", tags=["chat"])

engine = ChatEngine()


@router.post("/", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Smart natural language chat interface.
    Supports queries like:
    - "show me top 10 APIs"
    - "what's the slowest API right now?"
    - "show me errors from last Friday"
    - "is the checkout API slower today than yesterday?"
    - "what happened between 2pm and 3pm?"
    - "trace correlation id abc-123"
    - "are there any recurring errors?"
    - "check SLA for /api/orders"
    - "any recent deployments causing issues?"
    """
    result = engine.process_message(request.message, request.context)
    return ChatResponse(response=result["response"], data=result.get("data"))
