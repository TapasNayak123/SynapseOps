"""Auto-healing agent: fixes pipeline failures on the existing branch and updates the PR."""

from __future__ import annotations

import base64
import json
import logging

from bedrock_client import invoke_model
from github_client import (
    get_file_content, update_file, create_file,
    post_pr_comment, rerun_workflow, gh_headers,
    GITHUB_API, _get_session,
)
from config import TEAMS_WEBHOOK_URL, APP_BASE_URL
from app.services.notifier import _get_http, _WEBHOOK_RETRYABLE
from app.services.retry import retry_with_backoff

logger = logging.getLogger(__name__)


def find_pr_for_branch(repo: str, branch: str) -> dict | None:
    """Find an open PR associated with a branch."""
    url = f"{GITHUB_API}/repos/{repo}/pulls?state=open&head={repo.split('/')[0]}:{branch}"
    resp = _get_session().get(url, headers=gh_headers(), timeout=30)
    if resp.status_code == 200:
        prs = resp.json()
        if prs:
            return prs[0]
    return None


def generate_fix(repo: str, run: dict, failed_jobs: list, logs: str) -> dict:
    """Ask AI to generate a fix for the pipeline failure.

    Returns dict with:
        - fixable: bool
        - files: list of {path, action, content, explanation}
        - commit_message: str
        - explanation: str
    """
    job_info = "\n".join(
        f"- {j['name']}: {j['conclusion']}" for j in failed_jobs
    )

    failed_steps = []
    for job in failed_jobs:
        for step in job.get("steps", []):
            if step.get("conclusion") == "failure":
                failed_steps.append(f"  [{job['name']}] {step['name']}")

    # Try to extract file paths from error logs
    import re
    file_pattern = r'(?:at|in|from)\s+([a-zA-Z0-9_/.-]+\.(?:js|ts|jsx|tsx|py|java|go))'
    potential_files = re.findall(file_pattern, logs[:5000])
    
    # Fetch content of potential problem files
    file_contents = {}
    for file_path in set(potential_files[:3]):  # Limit to 3 files
        try:
            content = get_file_content(repo, file_path, run.get('head_branch', 'main'))
            if content:
                decoded = base64.b64decode(content['content']).decode('utf-8')
                file_contents[file_path] = decoded[:3000]  # Limit size
        except Exception:
            pass
    
    files_context = ""
    if file_contents:
        files_context = "\n\n## Current File Contents\n"
        for path, content in file_contents.items():
            files_context += f"\n### {path}\n```\n{content}\n```\n"

    prompt = f"""You are an Auto-Healing Agent for CI/CD pipelines. Analyze this failure
and generate a concrete code fix.

## Pipeline Info
- Repository: {repo}
- Workflow: {run.get('name', 'N/A')}
- Branch: {run.get('head_branch', 'N/A')}

## Failed Jobs
{job_info}

## Failed Steps
{chr(10).join(failed_steps) if failed_steps else '(none identified)'}

## Logs (truncated)
{logs[:10000]}
{files_context}

CRITICAL INSTRUCTIONS:
1. You MUST respond with ONLY valid JSON
2. NO markdown, NO code fences, NO explanations outside JSON
3. If fixable=true, you MUST provide complete file content in the "content" field
4. The "content" field must contain the ENTIRE file with the fix applied, not just the changes

Example of CORRECT response for a missing import:
{{
    "fixable": true,
    "explanation": "Missing logger import in app.js causing ReferenceError",
    "commit_message": "fix: add missing logger import",
    "files": [
        {{
            "path": "src/app.js",
            "action": "update",
            "content": "const express = require('express');\\nconst logger = require('./utils/logger');\\n\\nconst app = express();\\n\\napp.get('/', (req, res) => {{\\n  logger.info('Request received');\\n  res.send('Hello');\\n}});\\n\\nmodule.exports = app;",
            "explanation": "Added missing logger import at line 2"
        }}
    ]
}}

Example of CORRECT response for unfixable issue:
{{
    "fixable": false,
    "explanation": "This is a network timeout issue with external service, not fixable via code changes",
    "commit_message": "",
    "files": []
}}

Common fixable issues:
- Missing imports/requires → Add the import statement
- Syntax errors → Fix the syntax
- Undefined variables → Define or import them
- Test failures due to wrong assertions → Fix the test
- Lint errors → Fix formatting/style issues

NOT fixable:
- Network/timeout errors
- Permission/authentication issues
- Infrastructure problems
- External service outages

Now analyze the failure and respond with ONLY the JSON object:"""

    result = invoke_model(prompt, max_tokens=8000)

    # More aggressive cleaning of the response
    text = result.strip()
    
    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```)
        lines = lines[1:]
        # Remove last line if it's ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    
    # Remove any leading/trailing text before/after JSON
    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}") + 1
    
    if start != -1 and end > start:
        text = text[start:end]
    
    try:
        parsed = json.loads(text)
        
        # Validate the structure
        if not isinstance(parsed, dict):
            raise ValueError("Response is not a JSON object")
        
        # Ensure required fields exist
        if "fixable" not in parsed:
            parsed["fixable"] = False
        if "explanation" not in parsed:
            parsed["explanation"] = "Could not parse AI response properly"
        if "files" not in parsed:
            parsed["files"] = []
        if "commit_message" not in parsed:
            parsed["commit_message"] = "fix: auto-heal attempt"
        
        return parsed
        
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Failed to parse AI fix response: %s\nOriginal: %s", str(e), text[:500])
        
        # Try to extract useful information even if JSON parsing failed
        # Check if the AI said it's not fixable
        if "not fixable" in result.lower() or "cannot fix" in result.lower() or "infrastructure" in result.lower():
            return {
                "fixable": False,
                "explanation": "AI determined the issue is not auto-fixable (infrastructure or unclear root cause)",
                "files": [],
                "commit_message": ""
            }
        
        return {
            "fixable": False,
            "explanation": f"AI response was not valid JSON. Error: {str(e)}",
            "files": [],
            "commit_message": ""
        }


def apply_fix(repo: str, branch: str, fix: dict, run_id: int = None) -> dict:
    """Push fixes directly to the existing branch and comment on the associated PR.

    Returns dict with pr_url, pr_number, files_changed, rerun_triggered.
    """
    files_changed = []

    for file_info in fix.get("files", []):
        path = file_info["path"]
        content = file_info["content"]
        action = file_info.get("action", "update")
        content_b64 = base64.b64encode(content.encode()).decode()

        try:
            if action == "update":
                existing = get_file_content(repo, path, branch)
                file_sha = existing["sha"]
                update_file(
                    repo, path, content_b64,
                    message=f"🤖 auto-heal: {file_info.get('explanation', 'fix')}",
                    branch=branch,
                    file_sha=file_sha,
                )
            else:
                create_file(
                    repo, path, content_b64,
                    message=f"🤖 auto-heal: {file_info.get('explanation', 'new file')}",
                    branch=branch,
                )

            files_changed.append(path)
            logger.info("    Fixed: %s", path)

        except Exception:
            logger.exception("    Failed to fix: %s", path)

    if not files_changed:
        logger.warning("No files were changed — skipping")
        return {"pr_url": "", "pr_number": None, "files_changed": [], "rerun_triggered": False}

    # Find the associated PR and comment on it
    pr = find_pr_for_branch(repo, branch)
    pr_url = ""
    pr_number = None
    if pr:
        pr_number = pr["number"]
        pr_url = pr["html_url"]

        comment_body = f"""## 🔧 Auto-Heal: Fix Applied

The SynapseOps agent detected a pipeline failure and pushed a fix to this branch.

**Root Cause:** {fix.get('explanation', 'N/A')}

**Files Fixed:**
{chr(10).join(f'- `{f}`' for f in files_changed)}

The pipeline will re-run automatically with the new changes. Please review the fix.
"""
        try:
            post_pr_comment(repo, pr_number, comment_body)
            logger.info("    Commented on PR #%s", pr_number)
        except Exception:
            logger.exception("    Failed to comment on PR #%s", pr_number)

    # Pipeline re-runs automatically when we push to the branch
    # But if we have the run_id, we can also explicitly re-run failed jobs
    rerun_triggered = False
    if run_id:
        try:
            rerun_triggered = rerun_workflow(repo, run_id)
            if rerun_triggered:
                logger.info("    Re-triggered pipeline run %s", run_id)
        except Exception:
            logger.exception("    Failed to re-trigger pipeline")

    return {
        "pr_url": pr_url,
        "pr_number": pr_number,
        "files_changed": files_changed,
        "rerun_triggered": rerun_triggered,
    }


def send_autoheal_notification(repo: str, run: dict, fix: dict, result: dict):
    """Notify Teams about the auto-heal attempt."""
    if not TEAMS_WEBHOOK_URL:
        return

    branch = run.get("head_branch", "N/A")
    workflow = run.get("name", "N/A")
    files = ", ".join(result.get("files_changed", [])) or "None"

    if result.get("pr_url"):
        status_text = "✅ Fix Pushed to Existing Branch"
    elif result.get("files_changed"):
        status_text = "✅ Fix Pushed (no PR found)"
    else:
        status_text = "⚠️ Could Not Auto-Fix"

    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "Container",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": f"🔧 Auto-Heal: {status_text}",
                                    "size": "large",
                                    "weight": "bolder",
                                },
                            ],
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "📦 Repo", "value": repo},
                                {"title": "⚙️ Workflow", "value": workflow},
                                {"title": "🔀 Branch", "value": branch},
                                {"title": "📁 Files Fixed", "value": files},
                                {"title": "🔄 Pipeline Re-run", "value": "Yes" if result.get("rerun_triggered") else "Auto (on push)"},
                            ],
                        },
                        {
                            "type": "TextBlock",
                            "text": f"**Analysis:** {fix.get('explanation', 'N/A')[:500]}",
                            "wrap": True,
                            "size": "small",
                            "spacing": "medium",
                        },
                    ],
                    "actions": [],
                },
            }
        ],
    }

    if result.get("pr_url"):
        payload["attachments"][0]["content"]["actions"].append({
            "type": "Action.OpenUrl",
            "title": "🔗 View PR",
            "url": result["pr_url"],
        })

    payload["attachments"][0]["content"]["actions"].append({
        "type": "Action.OpenUrl",
        "title": "📊 Dashboard",
        "url": f"{APP_BASE_URL}/pipelines",
    })

    try:
        _send_autoheal_notification_with_retry(TEAMS_WEBHOOK_URL, payload)
    except Exception:
        logger.exception("❌ Failed to send auto-heal notification")


@retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=15.0, retryable_exceptions=_WEBHOOK_RETRYABLE)
def _send_autoheal_notification_with_retry(webhook_url: str, payload: dict):
    resp = _get_http().post(webhook_url, json=payload, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    logger.info("✅ Auto-heal notification sent")
