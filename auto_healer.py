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
    file_pattern = r'(?:at|in|from|File)\s+"?([a-zA-Z0-9_/.-]+\.(?:js|ts|jsx|tsx|py|java|go|json))"?'
    potential_files = re.findall(file_pattern, logs[:5000])
    
    # Also look for common patterns like "src/app.js:10:5"
    path_pattern = r'([a-zA-Z0-9_/.-]+\.(?:js|ts|jsx|tsx|py|java|go|json)):\d+'
    potential_files.extend(re.findall(path_pattern, logs[:5000]))
    
    # Fetch content of potential problem files
    file_contents = {}
    branch = run.get('head_branch', 'main')
    
    for file_path in set(potential_files[:5]):  # Limit to 5 files
        # Clean up the path
        file_path = file_path.strip().strip('"').strip("'")
        if not file_path or file_path.startswith('node_modules'):
            continue
            
        try:
            logger.info("Fetching file content: %s from branch %s", file_path, branch)
            content = get_file_content(repo, file_path, branch)
            if content:
                decoded = base64.b64decode(content['content']).decode('utf-8')
                file_contents[file_path] = {
                    'content': decoded,
                    'sha': content['sha']
                }
                logger.info("Successfully fetched %s (%d bytes)", file_path, len(decoded))
        except Exception as e:
            logger.warning("Could not fetch %s: %s", file_path, str(e))
    
    if not file_contents:
        logger.warning("No file contents could be fetched from error logs")
        return {
            "fixable": False,
            "explanation": "Could not identify or fetch the problematic files from the error logs",
            "files": [],
            "commit_message": ""
        }
    
    files_context = "\n\n## Current File Contents (from branch)\n"
    for path, info in file_contents.items():
        content_preview = info['content'][:2000]  # Limit for prompt
        files_context += f"\n### File: {path}\n```\n{content_preview}\n```\n"

    prompt = f"""You are an Auto-Healing Agent. A CI/CD pipeline failed. Your job is to fix the code.

## Pipeline Info
- Repository: {repo}
- Workflow: {run.get('name', 'N/A')}
- Branch: {branch}

## Failed Jobs
{job_info}

## Failed Steps
{chr(10).join(failed_steps) if failed_steps else '(none)'}

## Error Logs
{logs[:8000]}
{files_context}

## Your Task
1. Identify the root cause from the logs
2. If it's a code issue (syntax error, missing import, wrong logic), set fixable=true
3. If it's infrastructure (network, permissions, external service), set fixable=false
4. If fixable=true, provide the COMPLETE fixed file content

## Response Format (JSON only, no markdown)
{{
    "fixable": true,
    "explanation": "Brief explanation of the issue and fix",
    "commit_message": "fix: description",
    "files": [
        {{
            "path": "exact/path/from/above.js",
            "action": "update",
            "content": "COMPLETE file content with fix applied - must be valid code",
            "explanation": "What was changed"
        }}
    ]
}}

CRITICAL:
- If fixable=true, you MUST include at least one file with complete content
- Use exact file paths from the "Current File Contents" section above
- Provide the ENTIRE file, not just the changed lines
- Respond with ONLY the JSON object, nothing else"""

    try:
        result = invoke_model(prompt, max_tokens=10000)
        
        # Aggressive cleaning
        text = result.strip()
        
        # Remove markdown code fences
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        
        # Find JSON object
        start = text.find("{")
        end = text.rfind("}") + 1
        
        if start != -1 and end > start:
            text = text[start:end]
        
        parsed = json.loads(text)
        
        # Validate
        if not isinstance(parsed, dict):
            raise ValueError("Not a JSON object")
        
        # Add defaults
        parsed.setdefault("fixable", False)
        parsed.setdefault("explanation", "Unknown")
        parsed.setdefault("files", [])
        parsed.setdefault("commit_message", "fix: auto-heal")
        
        # Store file SHAs for later use
        if parsed.get("fixable") and parsed.get("files"):
            for file_info in parsed["files"]:
                path = file_info.get("path")
                if path in file_contents:
                    file_info["_sha"] = file_contents[path]["sha"]
        
        logger.info("AI response: fixable=%s, files=%d", 
                   parsed.get("fixable"), len(parsed.get("files", [])))
        
        return parsed
        
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("JSON parse error: %s\nResponse preview: %s", str(e), result[:500])
        
        # Fallback: check if AI said not fixable
        if any(word in result.lower() for word in ["not fixable", "cannot fix", "infrastructure", "network", "permission"]):
            return {
                "fixable": False,
                "explanation": "AI determined this is not a code issue that can be auto-fixed",
                "files": [],
                "commit_message": ""
            }
        
        return {
            "fixable": False,
            "explanation": f"Failed to parse AI response: {str(e)}",
            "files": [],
            "commit_message": ""
        }
    except Exception as e:
        logger.exception("Unexpected error in generate_fix")
        return {
            "fixable": False,
            "explanation": f"Error generating fix: {str(e)}",
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
                # Use stored SHA if available, otherwise fetch
                file_sha = file_info.get("_sha")
                if not file_sha:
                    existing = get_file_content(repo, path, branch)
                    file_sha = existing["sha"]
                
                logger.info("Updating file: %s (sha: %s)", path, file_sha[:8])
                update_file(
                    repo, path, content_b64,
                    message=f"🤖 auto-heal: {file_info.get('explanation', 'fix')}",
                    branch=branch,
                    file_sha=file_sha,
                )
            else:
                logger.info("Creating file: %s", path)
                create_file(
                    repo, path, content_b64,
                    message=f"🤖 auto-heal: {file_info.get('explanation', 'new file')}",
                    branch=branch,
                )

            files_changed.append(path)
            logger.info("    ✅ Fixed: %s", path)

        except Exception as e:
            logger.exception("    ❌ Failed to fix: %s - %s", path, str(e))

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

**Commit Message:** {fix.get('commit_message', 'N/A')}

The pipeline will re-run automatically with the new changes. Please review the fix.
"""
        try:
            post_pr_comment(repo, pr_number, comment_body)
            logger.info("    ✅ Commented on PR #%s", pr_number)
        except Exception:
            logger.exception("    Failed to comment on PR #%s", pr_number)

    # Pipeline re-runs automatically when we push to the branch
    # But if we have the run_id, we can also explicitly re-run failed jobs
    rerun_triggered = False
    if run_id:
        try:
            rerun_triggered = rerun_workflow(repo, run_id)
            if rerun_triggered:
                logger.info("    ✅ Re-triggered pipeline run %s", run_id)
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
