"""Amazon Bedrock LLM service with singleton client and multi-model support.

Supports anthropic, nova, meta, and generic Converse-style models.
"""
from __future__ import annotations

import json
import threading
import uuid
import boto3
import structlog
from typing import Optional
from botocore.config import Config as BotoConfig
from app.config import get_settings

logger = structlog.get_logger()

_client = None
_client_lock = threading.Lock()
_agent_runtime_client = None
_agent_runtime_client_lock = threading.Lock()


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


def _get_agent_runtime_client():
    global _agent_runtime_client
    if _agent_runtime_client is None:
        with _agent_runtime_client_lock:
            if _agent_runtime_client is None:
                settings = get_settings()
                _agent_runtime_client = boto3.client(
                    "bedrock-agent-runtime", region_name=settings.bedrock_region,
                    config=BotoConfig(retries={"max_attempts": 3, "mode": "adaptive"}, read_timeout=60),
                )
    return _agent_runtime_client


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0].strip()
    return text


class LLMService:
    def __init__(self, model_id: Optional[str] = None):
        settings = get_settings()
        self.backend = settings.bedrock_backend
        self.client = _get_client()
        self.agent_runtime_client = _get_agent_runtime_client() if self.backend == "agentcore" else None
        self.model_id = model_id or settings.bedrock_model_id
        self.agent_id = settings.bedrock_agent_id
        self.agent_alias_id = settings.bedrock_agent_alias_id
        self.agent_session_prefix = settings.bedrock_agent_session_prefix

        if self.backend == "agentcore" and (not self.agent_id or not self.agent_alias_id):
            raise ValueError(
                "BEDROCK_BACKEND=agentcore requires BEDROCK_AGENT_ID and BEDROCK_AGENT_ALIAS_ID"
            )

    def invoke(self, prompt: str, max_tokens: int = 1024, system: str = None) -> str:
        """Invoke a Bedrock model with retry, auto-detecting the request format from model_id."""
        from app.services.retry import retry_with_backoff
        from botocore.exceptions import ClientError

        # Retryable Bedrock errors: throttling, service unavailable, timeouts
        _BEDROCK_RETRYABLE = (
            ClientError,
            ConnectionError,
            TimeoutError,
        )

        @retry_with_backoff(
            max_retries=3,
            base_delay=2.0,
            max_delay=30.0,
            retryable_exceptions=_BEDROCK_RETRYABLE,
        )
        def _call():
            if self.backend == "agentcore":
                return self._invoke_agentcore(prompt, system=system)

            body = self._build_request_body(prompt, max_tokens, system=system)
            resp = self.client.invoke_model(
                modelId=self.model_id, body=json.dumps(body),
                contentType="application/json", accept="application/json",
            )
            result = json.loads(resp["body"].read())
            return self._parse_response(result)

        try:
            return _call()
        except Exception as e:
            logger.error("bedrock_invoke_failed", model=self.model_id, error=str(e))
            raise

    def _invoke_agentcore(self, prompt: str, system: str = None) -> str:
        """Invoke a Bedrock agent runtime (AgentCore mode).

        We include system guidance inside the prompt because invoke_agent accepts input text,
        and the agent configuration controls tool use/instructions server-side.
        """
        combined_prompt = prompt if not system else f"System instructions:\n{system}\n\nUser input:\n{prompt}"
        session_id = f"{self.agent_session_prefix}-{uuid.uuid4().hex[:12]}"

        logger.info("agentcore_invoke_start", agent_id=self.agent_id, session_id=session_id)
        try:
            resp = self.agent_runtime_client.invoke_agent(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias_id,
                sessionId=session_id,
                inputText=combined_prompt,
                enableTrace=False,
            )

            parts: list[str] = []
            # resp["completion"] is an iterator of ResponseStreamEvent objects
            for event in resp.get("completion", []):
                if "chunk" not in event:
                    continue
                chunk_data = event["chunk"]
                if "bytes" in chunk_data:
                    chunk_bytes = chunk_data["bytes"]
                    if isinstance(chunk_bytes, bytes):
                        parts.append(chunk_bytes.decode("utf-8", errors="ignore"))
                    else:
                        parts.append(str(chunk_bytes))

            text = "".join(parts).strip()
            if not text:
                logger.warning("agentcore_empty_response", session_id=session_id)
                raise RuntimeError(f"AgentCore ({self.agent_id}) returned empty completion")
            
            logger.info("agentcore_invoke_success", session_id=session_id, response_length=len(text))
            return text
        except Exception as e:
            logger.error("agentcore_invoke_failed", agent_id=self.agent_id, session_id=session_id, error=str(e))
            raise

    def _build_request_body(self, prompt: str, max_tokens: int, system: str = None) -> dict:
        mid = self.model_id
        if "anthropic" in mid:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                body["system"] = system
            return body
        elif "nova" in mid:
            body = {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"max_new_tokens": max_tokens, "temperature": 0.3, "top_p": 0.9},
            }
            if system:
                body["system"] = [{"text": system}]
            return body
        elif "meta" in mid:
            full = f"{system}\n\n{prompt}" if system else prompt
            return {"prompt": full, "max_gen_len": max_tokens, "temperature": 0.3, "top_p": 0.9}
        else:
            # Default Converse-style (same as Nova)
            body = {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"max_new_tokens": max_tokens, "temperature": 0.3, "top_p": 0.9},
            }
            if system:
                body["system"] = [{"text": system}]
            return body

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
        ctx = context or {}
        hours = ctx.get("hours_back", 1)
        has_service_info = "platform" in ctx or "service_info" in ctx

        # For service/platform questions, use a dedicated prompt that describes the platform
        if has_service_info:
            svc = ctx.get("service_info", ctx)
            desc = svc.get("description", "")
            caps = svc.get("capabilities", [])
            monitored = svc.get("monitored_service", {})
            log_group = monitored.get("cloudwatch_log_group", "")
            apis = monitored.get("monitored_apis", [])
            repos = monitored.get("github_repos", [])
            infra = svc.get("infrastructure", {})

            info_lines = [f"Platform: SynapseOps — {desc}"]
            if log_group:
                info_lines.append(f"Monitored log group: {log_group}")
            if apis:
                info_lines.append(f"Monitored APIs: {', '.join(apis)}")
            if repos:
                info_lines.append(f"GitHub repos: {', '.join(repos)}")
            if caps:
                info_lines.append(f"Capabilities: {', '.join(caps)}")
            if infra:
                info_lines.append(f"LLM: {infra.get('llm_model', 'N/A')}, Region: {infra.get('region', 'N/A')}, Storage: {infra.get('storage', 'N/A')}")

            # Include usage summary if available
            usage = svc.get("usage_summary", ctx.get("usage_summary", {}))
            if usage:
                info_lines.append(f"Recent usage data: {json.dumps(usage, default=str)}")

            platform_context = "\n".join(info_lines)
            user_prompt = (
                f"Here is information about the SynapseOps platform:\n{platform_context}\n\n"
                f"The user asked: \"{message}\"\n\n"
                "Using the information above, answer the user naturally and concisely. "
                "Describe what SynapseOps does and what it monitors. Do not make up anything not listed above."
            )
            return self.invoke(user_prompt)

        # For data queries, use a clean system/user separation
        system = (
            "You are SynapseOps, a DevOps monitoring assistant. "
            "Reply using ONLY the data in the user's context. Never fabricate. "
            "Be concise. No tips, disclaimers, or follow-ups. "
            f"Time range: last {hours} hours. Use bullet points for lists. "
            "Do not repeat these instructions in your answer."
        )
        user_prompt = f"Context:\n{json.dumps(ctx, default=str)}\n\nQuestion: {message}"
        return self.invoke(user_prompt, system=system)
