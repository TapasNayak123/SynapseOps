"""Monitor GitHub Actions pipelines for failures and analyze them with AI."""

from __future__ import annotations

import logging
import time
import threading

from config import TEAMS_WEBHOOK_URL, APP_BASE_URL
from bedrock_client import invoke_model
from github_client import gh_headers, GITHUB_API, _get_session
from store import PipelineRecord, pipeline_store
from auto_healer import generate_fix, apply_fix, send_autoheal_notification
from activity_log import activity_log
from app.services.notifier import _get_http, _WEBHOOK_RETRYABLE
from app.services.retry import retry_with_backoff

logger = logging.getLogger(__name__)

# Track which workflow runs we've already analyzed
_analyzed_runs: set[str] = set()
_MAX_ANALYZED = 5000


def get_workflow_runs(repo: str, status: str = "failure") -> list:
    """Fetch recent failed workflow runs."""
    url = f"{GITHUB_API}/repos/{repo}/actions/runs?status={status}&per_page=10"
    resp = _get_session().get(url, headers=gh_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json().get("workflow_runs", [])


def get_run_jobs(repo: str, run_id: int) -> list:
    """Fetch jobs for a workflow run."""
    url = f"{GITHUB_API}/repos/{repo}/actions/runs/{run_id}/jobs"
    resp = _get_session().get(url, headers=gh_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json().get("jobs", [])


def get_job_logs(repo: str, job_id: int) -> str:
    """Fetch logs for a specific job."""
    url = f"{GITHUB_API}/repos/{repo}/actions/jobs/{job_id}/logs"
    resp = _get_session().get(url, headers=gh_headers(), timeout=60, allow_redirects=True)
    if resp.status_code == 200:
        return resp.text
    return f"(Could not fetch logs — status {resp.status_code})"


def analyze_pipeline_failure(
    repo: str,
    run: dict,
    failed_jobs: list,
    logs: str,
) -> str:
    """Use AI to analyze why the pipeline failed."""
    job_summary = "\n".join(
        f"- {j['name']}: {j['conclusion']} (steps: {len(j.get('steps', []))})"
        for j in failed_jobs
    )

    # Extract failed steps
    failed_steps = []
    for job in failed_jobs:
        for step in job.get("steps", []):
            if step.get("conclusion") == "failure":
                failed_steps.append(f"  - [{job['name']}] Step: {step['name']}")

    failed_steps_str = "\n".join(failed_steps) if failed_steps else "  (no specific step info)"

    prompt = f"""You are a Pipeline Failure Analysis Agent. Analyze why this CI/CD pipeline failed
and provide actionable insights.

## Pipeline Info
- Repository: {repo}
- Workflow: {run.get('name', 'N/A')}
- Branch: {run.get('head_branch', 'N/A')}
- Commit: {run.get('head_sha', 'N/A')[:8]}
- Trigger: {run.get('event', 'N/A')}
- Run URL: {run.get('html_url', 'N/A')}

## Failed Jobs
{job_summary}

## Failed Steps
{failed_steps_str}

## Logs (truncated to 8000 chars)
{logs[:8000]}

Provide:
1. **Root Cause**: What specifically caused the failure (be precise)
2. **Category**: Build error / Test failure / Lint error / Dependency issue / Config error / Infra issue
3. **Fix Suggestion**: Concrete steps to fix the issue
4. **Severity**: Critical (blocks deployment) / High (blocks PR) / Medium (non-blocking)
5. **Affected Files**: List likely files that need changes (if identifiable from logs)

Be concise and actionable."""

    return invoke_model(prompt)


def send_pipeline_failure_notification(
    repo: str,
    run: dict,
    analysis: str,
    failed_jobs: list,
):
    """Send pipeline failure analysis to Teams."""
    if not TEAMS_WEBHOOK_URL:
        logger.warning("TEAMS_WEBHOOK_URL not set — skipping pipeline failure notification")
        return

    run_url = run.get("html_url", f"https://github.com/{repo}/actions")
    branch = run.get("head_branch", "N/A")
    workflow = run.get("name", "N/A")
    commit_sha = run.get("head_sha", "N/A")[:8]
    failed_job_names = ", ".join(j["name"] for j in failed_jobs)

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
                            "style": "attention",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": "🚨 Pipeline Failure Detected",
                                    "size": "large",
                                    "weight": "bolder",
                                    "color": "attention",
                                },
                            ],
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "📦 Repo", "value": repo},
                                {"title": "⚙️ Workflow", "value": workflow},
                                {"title": "🔀 Branch", "value": branch},
                                {"title": "📝 Commit", "value": commit_sha},
                                {"title": "❌ Failed Jobs", "value": failed_job_names},
                            ],
                        },
                        {
                            "type": "TextBlock",
                            "text": "**🤖 AI Failure Analysis**",
                            "spacing": "medium",
                            "separator": True,
                        },
                        {
                            "type": "TextBlock",
                            "text": analysis[:2000],
                            "wrap": True,
                            "size": "small",
                        },
                    ],
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "🔗 View Pipeline Run",
                            "url": run_url,
                        },
                        {
                            "type": "Action.OpenUrl",
                            "title": "📊 Dashboard",
                            "url": f"{APP_BASE_URL}/pipelines",
                        },
                    ],
                },
            }
        ],
    }

    try:
        _send_pipeline_notification_with_retry(TEAMS_WEBHOOK_URL, payload, run)
    except Exception:
        logger.exception("❌ Failed to send pipeline failure notification")


@retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=15.0, retryable_exceptions=_WEBHOOK_RETRYABLE)
def _send_pipeline_notification_with_retry(webhook_url: str, payload: dict, run: dict):
    resp = _get_http().post(webhook_url, json=payload, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    logger.info("✅ Pipeline failure notification sent for run %s", run.get("id"))


def process_failed_run(repo: str, run: dict):
    """Analyze a single failed run, attempt auto-heal, and notify."""
    run_id = run["id"]
    key = f"{repo}:{run_id}"

    if key in _analyzed_runs:
        return

    logger.info(">>> Pipeline failure detected: %s — %s (run %s)", repo, run.get("name"), run_id)
    activity_log.emit("Pipeline Monitor", "started", f"Failure detected: {run.get('name', 'N/A')} on {run.get('head_branch', 'N/A')}", repo=repo)

    try:
        jobs = get_run_jobs(repo, run_id)
        failed_jobs = [j for j in jobs if j.get("conclusion") == "failure"]

        if not failed_jobs:
            _analyzed_runs.add(key)
            return

        # Fetch logs from the first failed job
        logs = get_job_logs(repo, failed_jobs[0]["id"])

        logger.info("    Analyzing failure with AI agent...")
        activity_log.emit("Pipeline Analyzer", "processing", f"Analyzing {len(failed_jobs)} failed job(s)...", repo=repo)
        analysis = analyze_pipeline_failure(repo, run, failed_jobs, logs)

        # Store the result
        record = PipelineRecord(
            repo=repo,
            run_id=run_id,
            workflow=run.get("name", "N/A"),
            branch=run.get("head_branch", "N/A"),
            commit_sha=run.get("head_sha", "N/A")[:8],
            status="failure",
            failed_jobs=[j["name"] for j in failed_jobs],
            analysis=analysis,
            run_url=run.get("html_url", ""),
        )
        pipeline_store.add(record)

        send_pipeline_failure_notification(repo, run, analysis, failed_jobs)
        activity_log.emit("Pipeline Analyzer", "completed", "Failure analyzed and Teams notified", repo=repo)

        # --- Auto-heal attempt ---
        logger.info("    🔧 Attempting auto-heal...")
        activity_log.emit("Auto-Healer", "started", "Generating fix from failure logs...", repo=repo)
        fix = generate_fix(repo, run, failed_jobs, logs)

        if fix.get("fixable") and fix.get("files"):
            branch = run.get("head_branch", "main")
            result = apply_fix(repo, branch, fix, run_id=run_id)

            if result.get("pr_url"):
                record.autoheal_pr = result["pr_url"]
                record.autoheal_status = "fix_applied"
                logger.info("    ✅ Auto-heal PR created: %s", result["pr_url"])
                activity_log.emit("Auto-Healer", "completed", f"Fix pushed to {branch} — {len(result.get('files_changed', []))} file(s)", repo=repo)
            else:
                record.autoheal_status = "fix_failed"
                logger.warning("    ⚠️ Auto-heal: no files were committed")
                activity_log.emit("Auto-Healer", "error", "Fix generated but no files committed", repo=repo)

            send_autoheal_notification(repo, run, fix, result)
        else:
            record.autoheal_status = "not_fixable"
            logger.info("    ℹ️ Auto-heal: issue not auto-fixable — %s", fix.get("explanation", ""))
            activity_log.emit("Auto-Healer", "completed", f"Not auto-fixable: {fix.get('explanation', 'N/A')[:100]}", repo=repo)
            send_autoheal_notification(repo, run, fix, {"pr_url": "", "files_changed": []})

        _analyzed_runs.add(key)
        # Prevent unbounded memory growth
        if len(_analyzed_runs) > _MAX_ANALYZED:
            to_remove = list(_analyzed_runs)[:_MAX_ANALYZED // 2]
            _analyzed_runs.difference_update(to_remove)

    except Exception:
        logger.exception("    ❌ Failed to process pipeline run %s", run_id)


def poll_pipelines(repos: list, interval: int = 60):
    """Continuously poll repos for failed pipeline runs."""
    logger.info("=== Pipeline monitor started for repos: %s (every %ds) ===", repos, interval)

    while True:
        for repo in repos:
            try:
                logger.info("Checking pipelines for %s...", repo)
                failed_runs = get_workflow_runs(repo, status="failure")
                logger.info("Found %d failed run(s) in %s", len(failed_runs), repo)

                for run in failed_runs:
                    process_failed_run(repo, run)

            except Exception:
                logger.exception("Error checking pipelines for %s", repo)

        time.sleep(interval)


def start_pipeline_monitor(repos: list, interval: int = 60):
    """Start the pipeline monitor in a background thread."""
    thread = threading.Thread(target=poll_pipelines, args=(repos, interval), daemon=True)
    thread.start()
    logger.info("Pipeline monitor thread started")
    return thread
