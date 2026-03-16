"""Amazon Bedrock LLM service with singleton client."""
import json
import boto3
import structlog
from botocore.config import Config as BotoConfig
from app.config import get_settings

logger = structlog.get_logger()

_client = None


def _get_client():
    global _client
    if _client is None:
        settings = get_settings()
        _client = boto3.client(
            "bedrock-runtime", region_name=settings.bedrock_region,
            config=BotoConfig(retries={"max_attempts": 3, "mode": "adaptive"}, read_timeout=60),
        )
    return _client


class LLMService:
    def __init__(self):
        self.client = _get_client()
        self.model_id = get_settings().bedrock_model_id

    def invoke(self, prompt: str, max_tokens: int = 1024) -> str:
        try:
            resp = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                }),
                contentType="application/json", accept="application/json",
            )
            return json.loads(resp["body"].read())["content"][0]["text"]
        except Exception as e:
            logger.error("bedrock_invoke_failed", error=str(e))
            raise

    def analyze_error(self, error_message: str, stack_trace: str = "") -> dict:
        prompt = f"""You are a senior backend engineer. Analyze this error:
Error: {error_message}
Stack trace: {stack_trace}

Respond in JSON: {{"root_cause": "...", "is_auto_fixable": true/false, "suggested_fix": "...", "confidence": 0.0, "explanation": "..."}}"""
        try:
            return json.loads(self.invoke(prompt))
        except json.JSONDecodeError:
            return {"root_cause": "Analysis failed", "is_auto_fixable": False, "confidence": 0.0}

    def chat(self, message: str, context: dict = None) -> str:
        system = """You are SynapseOps, a CloudWatch monitoring assistant. You help engineers understand API performance, errors, and logs. Answer concisely and technically."""
        return self.invoke(f"{system}\n\nContext: {json.dumps(context or {}, default=str)}\n\nUser: {message}")
