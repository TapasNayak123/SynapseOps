"""Amazon Bedrock client for invoking foundation models."""

from __future__ import annotations

import json
import boto3
from config import AWS_REGION, BEDROCK_MODEL_ID

bedrock_runtime = boto3.client("bedrock-runtime", region_name=AWS_REGION)


def invoke_model(prompt: str, max_tokens: int = 4096) -> str:
    """Invoke a Bedrock model with the given prompt and return the response text."""
    model_id = BEDROCK_MODEL_ID

    if "anthropic" in model_id:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        })
    elif "nova" in model_id:
        body = json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {
                "max_new_tokens": max_tokens,
                "temperature": 0.7,
                "top_p": 0.9,
            },
        })
    elif "meta" in model_id:
        body = json.dumps({
            "prompt": prompt,
            "max_gen_len": max_tokens,
            "temperature": 0.7,
            "top_p": 0.9,
        })
    else:
        # Default: use Converse-style messages format
        body = json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {
                "max_new_tokens": max_tokens,
                "temperature": 0.7,
                "top_p": 0.9,
            },
        })

    response = bedrock_runtime.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    result = json.loads(response["body"].read())

    if "anthropic" in model_id:
        return result["content"][0]["text"]
    elif "nova" in model_id:
        return result["output"]["message"]["content"][0]["text"]
    elif "meta" in model_id:
        return result["generation"]
    else:
        return result["output"]["message"]["content"][0]["text"]
