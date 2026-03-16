"""Amazon Bedrock LLM service with singleton client and multi-model support.

Supports anthropic, nova, meta, and generic Converse-style models.
"""
import json
import threading
import boto3
import structlog
from botocore.config import Config as BotoConfig
from app.config import get_settings

logger = structlog.get_logger()

_client = None
_client_lock = threading.Lock()


def _get_client():
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                settings = get_settings()
                _client = boto3.client(
                    "bedrock-runtime", region_name=settings.bedrock_region,
                    config=BotoConfig(retries={"max_attempts": 3, "mode": "adaptive"}, read_timeout=60),
                )
    return _client


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0].strip()
    return text


class LLMService:
    def __init__(self, model_id: str | None = None):
        self.client = _get_client()
        self.model_id = model_id or get_settings().bedrock_model_id

    def invoke(self, prompt: str, max_tokens: int = 1024) -> str:
        """Invoke a Bedrock model, auto-detecting the request format from model_id."""
        try:
            body = self._build_request_body(prompt, max_tokens)
            resp = self.client.invoke_model(
                modelId=self.model_id, body=json.dumps(body),
                contentType="application/json", accept="application/json",
            )
            result = json.loads(resp["body"].read())
            return self._parse_response(result)
        except Exception as e:
            logger.error("bedrock_invoke_failed", model=self.model_id, error=str(e))
            raise

    def _build_request_body(self, prompt: str, max_tokens: int) -> dict:
        mid = self.model_id
        if "anthropic" in mid:
            return {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
        elif "nova" in mid:
            return {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"max_new_tokens": max_tokens, "temperature": 0.7, "top_p": 0.9},
            }
        elif "meta" in mid:
            return {"prompt": prompt, "max_gen_len": max_tokens, "temperature": 0.7, "top_p": 0.9}
        else:
            # Default Converse-style
            return {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"max_new_tokens": max_tokens, "temperature": 0.7, "top_p": 0.9},
            }

    def _parse_response(self, result: dict) -> str:
        mid = self.model_id
        if "anthropic" in mid:
            return result["content"][0]["text"]
        elif "nova" in mid:
            return result["output"]["message"]["content"][0]["text"]
        elif "meta" in mid:
            return result["generation"]
        else:
            return result["output"]["message"]["content"][0]["text"]

    def analyze_error(self, error_message: str, stack_trace: str = "") -> dict:
        prompt = f"""You are a senior backend engineer. Analyze this error:
Error: {error_message[:2000]}
Stack trace: {stack_trace[:4000]}

Respond in JSON: {{"root_cause": "...", "is_auto_fixable": true/false, "suggested_fix": "...", "confidence": 0.0, "explanation": "..."}}"""
        try:
            text = _strip_code_fences(self.invoke(prompt))
            return json.loads(text)
        except json.JSONDecodeError:
            return {"root_cause": "Analysis failed — invalid JSON response", "is_auto_fixable": False, "confidence": 0.0}
        except Exception as e:
            return {"root_cause": f"Analysis failed: {e}", "is_auto_fixable": False, "confidence": 0.0}

    def chat(self, message: str, context: dict = None) -> str:
        system = """You are SynapseOps, a CloudWatch monitoring assistant. You help engineers understand API performance, errors, and logs. Answer concisely and technically."""
        return self.invoke(f"{system}\n\nContext: {json.dumps(context or {}, default=str)}\n\nUser: {message}")
