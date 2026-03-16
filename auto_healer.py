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
from app.services.notifier import _get_http

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

Respond in STRICT JSON format (no markdown, no code fences):
{{
    "fixable": true or false,
    "explanation": "one paragraph explaining the root cause and fix",
    "commit_message": "fix: short description of the fix",
    "files": [
        {{
            "path": "relative/path/to/file",
            "action": "update" or "create",
            "content": "full file content with the fix applied",
            "explanation": "what was changed and why"
        }}
    ]
}}

Rules:
- Set fixable=false if the issue is infrastructure-related (network, permissions, service outage)
- Set fixable=false if you cannot determine the exact fix from the logs
- Only include files you are confident need changing
- Provide the COMPLETE file content for each file, not just the diff
- Common fixable issues: syntax errors, missing imports, test failures, lint errors, dependency versions
- If fixable=true, you MUST include at least one file in the files array"""

    result = invoke_model(prompt, max_tokens=8000)

    text = result.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error("Failed to parse AI fix response: %s", text[:500])
        return {"fixable": False, "explanation": "AI response was not valid JSON", "files": [], "commit_message": ""}


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
        resp = _get_http().post(
            TEAMS_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        logger.info("✅ Auto-heal notification sent")
    except Exception:
        logger.exception("❌ Failed to send auto-heal notification")
