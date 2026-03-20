"""Pydantic models for API request/response schemas."""
from pydantic import BaseModel
from typing import Optional
from enum import Enum


class HttpStatusCategory(str, Enum):
    SUCCESS_2XX = "2xx"
    REDIRECT_3XX = "3xx"
    CLIENT_ERROR_4XX = "4xx"
    SERVER_ERROR_5XX = "5xx"


class ChatRequest(BaseModel):
    message: str
    context: Optional[dict] = None


class ChatResponse(BaseModel):
    response: str
    data: Optional[dict] = None
    intent: Optional[dict] = None
