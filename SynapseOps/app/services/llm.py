import json
import boto3
import structlog
from app.config import get_settings

logger = structlog.get_logger()


class LLMService:
    def __init__(self):
        settings = get_settings()
        self.client = boto3.client("bedrock-runtime", region_name=settings.bedrock_region)
        self.model_id = settings.bedrock_model_id

    def invoke(self, prompt: str, max_tokens: int = 1024) -> str:
        """Invoke Bedrock LLM with a prompt."""
        try:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            })

            response = self.client.invoke_model(
                modelId=self.model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )

            result = json.loads(response["body"].read())
            return result["content"][0]["text"]
        except Exception as e:
            logger.error("bedrock_invoke_failed", error=str(e))
            raise

    def analyze_error(self, error_message: str, stack_trace: str = "") -> dict:
        """Use LLM to analyze an error and suggest a fix."""
        prompt = f"""You are a senior backend engineer. Analyze this error and provide:
1. Root cause analysis
2. Whether this is an auto-fixable issue (simple config, typo, missing null check, etc.)
3. Suggested code fix if applicable
4. Confidence level (0.0 to 1.0)

Error: {error_message}
Stack trace: {stack_trace}

Respond in JSON format:
{{"root_cause": "...", "is_auto_fixable": true/false, "suggested_fix": "...", "confidence": 0.0, "explanation": "..."}}"""

        try:
            response = self.invoke(prompt)
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "root_cause": response if response else "Analysis failed",
                "is_auto_fixable": False,
                "suggested_fix": None,
                "confidence": 0.0,
                "explanation": "Could not parse LLM response as JSON",
            }

    def chat(self, message: str, context: dict = None) -> str:
        """Handle natural language chat queries about the service."""
        system_context = """You are a CloudWatch monitoring assistant. You help engineers
understand their API performance, errors, and logs. You have access to:
- API metrics (error rates, latency, throughput)
- Error logs grouped by HTTP status code
- Correlation ID tracing
- Slow API analysis
- Top API usage stats

Answer concisely and technically. If you need specific data, say what query you'd run."""

        prompt = f"{system_context}\n\nContext: {json.dumps(context or {})}\n\nUser: {message}"
        return self.invoke(prompt)
