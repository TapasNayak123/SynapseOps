"""SynapseOps — Unified application (FastAPI).

Combines the PR analysis dashboard, GitHub webhook receiver, API monitoring,
chat engine, and auto-fix services into a single server.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
import structlog

from app.config import get_settings, validate_settings_on_startup
from app.routes import metrics, chat, alerts, websockets
from app.tasks.scheduler import start_scheduler, stop_scheduler

# Root-level imports (PR analysis pipeline)
from config import GITHUB_WEBHOOK_SECRET
from github_client import get_pr_details, get_pr_diff, get_pr_files, post_pr_comment, merge_pr
from agents import supervisor, check_and_generate_description
from conflict_detector import check_conflicts
from store import pr_store, pipeline_store
from pipeline_monitor import process_failed_run
from activity_log import activity_log
from app.services.deployment_gate import get_deployment_gate
from app.services.dedup import is_duplicate, pr_key, pipeline_key, deploy_key, delivery_key

structlog.configure(processors=[
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.add_log_level,
    structlog.processors.JSONRenderer(),
])
logger = structlog.get_logger()
py_logger = logging.getLogger("synapse-ops")

# Template directories
ROOT_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = ROOT_DIR / "templates"
STATIC_DIR = Path(__file__).parent / "static"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _seed_monitored_apis():
    settings = get_settings()
    if settings.monitored_apis:
        try:
            from app.services.cache import CacheService
            cache = CacheService()
            if not cache.get("monitored_apis"):
                apis = [a.strip() for a in settings.monitored_apis.split(",") if a.strip()]
                cache.set("monitored_apis", apis, ttl_seconds=86400 * 30)
                logger.info("seeded_apis", count=len(apis))
        except Exception as e:
            logger.warning("seed_apis_skipped", error=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting")

    # Validate configuration and log warnings
    for warning in validate_settings_on_startup():
        py_logger.warning("CONFIG: %s", warning)
        logger.warning("config_warning", msg=warning)

    _seed_monitored_apis()

    # Start APScheduler (monitoring jobs)
    try:
        start_scheduler()
    except Exception as e:
        logger.warning("scheduler_start_failed", error=str(e))

    py_logger.info("Webhook mode active — listening on /webhook for PR and pipeline events.")

    # Store event loop reference so background threads can broadcast to WebSocket
    import asyncio as _aio
    activity_log.set_event_loop(_aio.get_running_loop())

    yield

    try:
        stop_scheduler()
    except Exception as e:
        logger.warning("scheduler_stop_failed", error=str(e))
    logger.info("stopped")


app = FastAPI(title="SynapseOps", version="1.0.0", lifespan=lifespan)

# Prevent browser caching of HTML pages (avoids stale chat widget)

class NoCacheHTMLMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        ct = response.headers.get("content-type", "")
        if "text/html" in ct:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

app.add_middleware(NoCacheHTMLMiddleware)

# Include FastAPI routers (monitoring, chat, alerts, websockets)
app.include_router(metrics.router)
app.include_router(chat.router)
app.include_router(alerts.router)
app.include_router(websockets.router)

# Static files
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Health endpoints ──────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "healthy", "service": "synapse-ops"}


@app.get("/health/ready")
def readiness():
    from app.services.cache import CacheService
    from app.services.dynamodb import DynamoDBService
    try:
        r = CacheService().ping()
    except Exception:
        r = False
    try:
        d = DynamoDBService().ping()
    except Exception:
        d = False
    return {"status": "ready" if r and d else "degraded",
            "redis": "ok" if r else "error", "dynamodb": "ok" if d else "error"}


# ── Dashboard routes ───────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    records = pr_store.all()
    stats = pr_store.stats()
    return templates.TemplateResponse("dashboard.html", {"request": request, "records": records, "stats": stats})


@app.get("/metrics", response_class=HTMLResponse)
def metrics_page(request: Request):
    m = pr_store.metrics()
    return templates.TemplateResponse("metrics.html", {"request": request, "m": m})


@app.get("/pr/{repo:path}/{pr_number:int}", response_class=HTMLResponse)
def pr_detail(request: Request, repo: str, pr_number: int):
    record = pr_store.get(repo, pr_number)
    if not record:
        raise HTTPException(status_code=404, detail="PR not found")
    return templates.TemplateResponse("pr_detail.html", {"request": request, "pr": record})


@app.get("/activity", response_class=HTMLResponse)
def activity_page(request: Request):
    entries = activity_log.all()
    return templates.TemplateResponse("activity.html", {"request": request, "entries": entries})


@app.get("/pipelines", response_class=HTMLResponse)
def pipelines_dashboard(request: Request):
    records = pipeline_store.all()
    stats = pipeline_store.stats()
    return templates.TemplateResponse("pipelines.html", {"request": request, "records": records, "stats": stats})


@app.get("/pipeline/{repo:path}/{run_id:int}", response_class=HTMLResponse)
def pipeline_detail(request: Request, repo: str, run_id: int):
    record = pipeline_store.get(repo, run_id)
    if not record:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return templates.TemplateResponse("pipeline_detail.html", {"request": request, "p": record})


# ── Test page ─────────────────────────────────────────────────────────────

@app.get("/test", response_class=HTMLResponse)
def test_pr_get(request: Request):
    return templates.TemplateResponse("test.html", {"request": request, "result": None, "error": None, "form_repo": "", "form_pr_number": ""})


@app.post("/test", response_class=HTMLResponse)
def test_pr_post(request: Request, repo: str = Form(""), pr_number: str = Form(""), post_comment: str = Form(None)):
    repo = repo.strip()
    pr_number_str = pr_number.strip()
    ctx = {"request": request, "form_repo": repo, "form_pr_number": pr_number_str}

    if not repo or not pr_number_str:
        return templates.TemplateResponse("test.html", {**ctx, "result": None, "error": "Repo and PR number are required."})

    # Accept full GitHub URLs
    repo = repo.rstrip("/")
    if "github.com" in repo:
        parts = repo.split("github.com/")[-1].split("/")
        if len(parts) >= 2:
            repo = f"{parts[0]}/{parts[1]}"

    try:
        pr_num = int(pr_number_str)
        py_logger.info("Test PR: Starting analysis for %s #%s", repo, pr_num)
        
        pr_details = get_pr_details(repo, pr_num)
        py_logger.info("Test PR: Fetched PR details")
        
        diff = get_pr_diff(repo, pr_num)
        py_logger.info("Test PR: Fetched diff (%d chars)", len(diff))
        
        files = get_pr_files(repo, pr_num)
        py_logger.info("Test PR: Fetched %d files", len(files))

        desc_generated = check_and_generate_description(pr_details, diff, files, repo, pr_num)
        py_logger.info("Test PR: Description check complete (generated=%s)", desc_generated)
        
        conflicts = check_conflicts(repo, pr_num, files,
                                    pr_title=pr_details.get("title", ""),
                                    pr_author=pr_details.get("user", {}).get("login", ""))
        py_logger.info("Test PR: Conflict check complete (%d conflicts)", len(conflicts))
        
        summary = supervisor(pr_details, diff, files, repo, pr_num)
        py_logger.info("Test PR: Supervisor complete, summary length=%d", len(summary))

        posted = False
        if post_comment:
            py_logger.info("Test PR: Posting comment to GitHub...")
            post_pr_comment(repo, pr_num, summary)
            posted = True
            py_logger.info("Test PR: Comment posted successfully")

        py_logger.info("Test PR: Analysis complete for %s #%s", repo, pr_num)
        return templates.TemplateResponse("test.html", {**ctx, "result": {
            "summary": summary, "posted": posted, "repo": repo,
            "pr_number": pr_num, "desc_generated": desc_generated, "conflicts": conflicts,
        }, "error": None})
    except Exception as e:
        py_logger.exception("Test failed for %s #%s", repo, pr_number_str)
        return templates.TemplateResponse("test.html", {**ctx, "result": None, "error": str(e)})


# ── API routes (PR data) ─────────────────────────────────────────────────

@app.get("/api/stats")
def api_stats():
    return pr_store.stats()


@app.get("/api/pr-metrics")
def api_pr_metrics():
    return pr_store.metrics()


@app.get("/api/prs")
def api_prs():
    records = pr_store.all()
    return [
        {
            "repo": r.repo, "pr_number": r.pr_number, "title": r.title,
            "author": r.author, "risk_level": r.risk_level,
            "files_changed": r.files_changed, "total_duration_ms": r.total_duration_ms,
            "timestamp": r.timestamp, "pr_type": r.pr_type, "priority": r.priority,
        }
        for r in records
    ]


@app.get("/api/activity")
def api_activity(since: int = Query(0)):
    entries, cursor = activity_log.since(since)
    return {"entries": activity_log.to_dicts(entries), "cursor": cursor}


@app.get("/api/pipelines")
def api_pipelines():
    """Get pipeline data for AJAX updates."""
    records = pipeline_store.all()
    stats = pipeline_store.stats()
    return {
        "pipelines": [
            {
                "repo": r.repo,
                "run_id": r.run_id,
                "workflow": r.workflow,
                "status": r.status,
                "conclusion": r.status,
                "timestamp": r.timestamp,
            }
            for r in records[:20]  # Limit to recent 20
        ],
        "stats": stats
    }


# ── Deployment Gate API ──────────────────────────────────────────────────

@app.get("/api/deployment-gate/status")
def deployment_gate_status():
    """Get current deployment gate analysis and held deployments."""
    gate = get_deployment_gate()
    analysis = gate._analyze_current_conditions()
    held = gate.get_held_deployments()
    return {"current_conditions": analysis, "held_deployments": held}


@app.get("/api/deployment-gate/held")
def deployment_gate_held():
    """List all held deployments."""
    return get_deployment_gate().get_held_deployments()


# ── PR Action endpoints (Teams card callbacks) ───────────────────────────

@app.get("/action/approve/{repo:path}/{pr_number:int}", response_class=HTMLResponse)
def action_approve_get(request: Request, repo: str, pr_number: int):
    return templates.TemplateResponse("action.html", {"request": request,
        "action_type": "approve", "action_title": "Approve & Merge PR",
        "action_emoji": "✅", "repo": repo, "pr_number": pr_number,
        "result": None, "success": None})


@app.post("/action/approve/{repo:path}/{pr_number:int}", response_class=HTMLResponse)
def action_approve_post(request: Request, repo: str, pr_number: int):
    try:
        merge_pr(repo, pr_number, commit_title=f"Approved and merged via AI Agent (PR #{pr_number})")
        post_pr_comment(repo, pr_number, "✅ **Approved and merged** via AI PR Summary Agent from Microsoft Teams.")
        py_logger.info("PR #%s on %s merged via Teams approval", pr_number, repo)
        return templates.TemplateResponse("action.html", {"request": request,
            "action_type": "approve", "action_title": "Approve & Merge PR",
            "action_emoji": "✅", "repo": repo, "pr_number": pr_number,
            "result": f"PR #{pr_number} merged successfully!", "success": True})
    except Exception as e:
        py_logger.exception("Failed to merge PR #%s", pr_number)
        return templates.TemplateResponse("action.html", {"request": request,
            "action_type": "approve", "action_title": "Approve & Merge PR",
            "action_emoji": "✅", "repo": repo, "pr_number": pr_number,
            "result": f"Failed to merge: {e}", "success": False})


@app.get("/action/reject/{repo:path}/{pr_number:int}", response_class=HTMLResponse)
def action_reject_get(request: Request, repo: str, pr_number: int):
    return templates.TemplateResponse("action.html", {"request": request,
        "action_type": "reject", "action_title": "Request Changes",
        "action_emoji": "🔴", "repo": repo, "pr_number": pr_number,
        "result": None, "success": None})


@app.post("/action/reject/{repo:path}/{pr_number:int}", response_class=HTMLResponse)
def action_reject_post(request: Request, repo: str, pr_number: int, reason: str = Form("")):
    reason = reason.strip() or "Changes requested by reviewer via AI PR Summary Agent."
    try:
        post_pr_comment(repo, pr_number, f"🔴 **Changes Requested** (via Teams)\n\n{reason}")
        py_logger.info("Changes requested on PR #%s on %s via Teams", pr_number, repo)
        return templates.TemplateResponse("action.html", {"request": request,
            "action_type": "reject", "action_title": "Request Changes",
            "action_emoji": "🔴", "repo": repo, "pr_number": pr_number,
            "result": f"Changes requested on PR #{pr_number}.", "success": True})
    except Exception as e:
        py_logger.exception("Failed to request changes on PR #%s", pr_number)
        return templates.TemplateResponse("action.html", {"request": request,
            "action_type": "reject", "action_title": "Request Changes",
            "action_emoji": "🔴", "repo": repo, "pr_number": pr_number,
            "result": f"Failed: {e}", "success": False})


@app.post("/api/pr/approve")
async def api_approve_and_merge(request: Request):
    data = await request.json()
    repo = data.get("repo", "")
    pr_number = data.get("pr_number")
    if not repo or not pr_number:
        raise HTTPException(status_code=400, detail="repo and pr_number required")
    try:
        pr_number = int(pr_number)
        result = merge_pr(repo, pr_number, commit_title=f"Approved and merged via AI Agent (PR #{pr_number})")
        post_pr_comment(repo, pr_number, "✅ **Approved and merged** via AI PR Summary Agent from Microsoft Teams.")
        return {"message": f"PR #{pr_number} merged successfully", "sha": result.get("sha", "")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pr/reject")
async def reject_pr(request: Request):
    data = await request.json()
    repo = data.get("repo", "")
    pr_number = data.get("pr_number")
    reason = data.get("reason", "Changes requested by reviewer via AI PR Summary Agent.")
    if not repo or not pr_number:
        raise HTTPException(status_code=400, detail="repo and pr_number required")
    try:
        pr_number = int(pr_number)
        post_pr_comment(repo, pr_number, f"🔴 **Changes Requested** (via Teams)\n\n{reason}")
        return {"message": f"Changes requested on PR #{pr_number}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GitHub Webhook ────────────────────────────────────────────────────────

# ── Background processing helpers ─────────────────────────────────────────

def _run_in_background(fn, *args):
    """Spawn a daemon thread to run *fn* so the webhook returns 202 immediately."""
    t = threading.Thread(target=fn, args=args, daemon=True)
    t.start()


def _process_pr(repo_full_name, pr_number, pr_payload):
    """Heavy PR analysis pipeline — runs in a background thread."""
    try:
        py_logger.info("Background: analysing PR #%s on %s", pr_number, repo_full_name)
        pr_details = get_pr_details(repo_full_name, pr_number)
        diff = get_pr_diff(repo_full_name, pr_number)
        files = get_pr_files(repo_full_name, pr_number)

        check_and_generate_description(pr_details, diff, files, repo_full_name, pr_number)
        check_conflicts(
            repo_full_name, pr_number, files,
            pr_title=pr_details.get("title", ""),
            pr_author=pr_details.get("user", {}).get("login", ""),
        )
        summary = supervisor(pr_details, diff, files, repo_full_name, pr_number)
        post_pr_comment(repo_full_name, pr_number, summary)
        py_logger.info("Background: finished PR #%s on %s", pr_number, repo_full_name)
    except Exception:
        py_logger.exception("Background: failed processing PR #%s on %s", pr_number, repo_full_name)


def _process_pipeline(repo_full_name, run):
    """Handle a failed workflow run — runs in a background thread."""
    try:
        py_logger.info("Background: processing pipeline failure %s run %s", repo_full_name, run.get("id"))
        process_failed_run(repo_full_name, run)
        py_logger.info("Background: finished pipeline failure %s run %s", repo_full_name, run.get("id"))
    except Exception:
        py_logger.exception("Background: failed processing pipeline %s run %s", repo_full_name, run.get("id"))


def _process_deployment_gate(repo_full_name, run):
    """Evaluate deployment gate for a successful workflow run — runs in a background thread."""
    try:
        gate = get_deployment_gate()
        run_id = run.get("id", 0)
        py_logger.info("Background: evaluating deployment gate for %s run %s", repo_full_name, run_id)
        gate.evaluate(
            repo=repo_full_name,
            run_id=run_id,
            workflow=run.get("name", "N/A"),
            branch=run.get("head_branch", "N/A"),
            commit_sha=run.get("head_sha", "")[:8],
            sender=run.get("actor", {}).get("login", "unknown"),
        )
        py_logger.info("Background: finished deployment gate for %s run %s", repo_full_name, run_id)
    except Exception:
        py_logger.exception("Background: deployment gate failed for %s run %s", repo_full_name, run.get("id"))


def _process_deployment_event(repo_full_name, deployment, sender):
    """Evaluate deployment gate for a deployment event — runs in a background thread."""
    try:
        gate = get_deployment_gate()
        dep_id = deployment.get("id", 0)
        py_logger.info("Background: evaluating deployment event for %s id %s", repo_full_name, dep_id)
        gate.evaluate(
            repo=repo_full_name,
            run_id=dep_id,
            workflow=deployment.get("task", "deployment"),
            branch=deployment.get("ref", "N/A"),
            commit_sha=deployment.get("sha", "")[:8],
            sender=sender,
        )
        py_logger.info("Background: finished deployment event for %s id %s", repo_full_name, dep_id)
    except Exception:
        py_logger.exception("Background: deployment event failed for %s", repo_full_name)


def _verify_signature(payload: bytes, signature: str) -> bool:
    if not GITHUB_WEBHOOK_SECRET:
        py_logger.warning("GITHUB_WEBHOOK_SECRET not set — skipping signature verification")
        return True
    expected = "sha256=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/webhook", status_code=202)
async def webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(body, signature):
        py_logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # ── Delivery-level dedup (catches exact GitHub retries) ───────────
    gh_delivery = request.headers.get("X-GitHub-Delivery", "")
    if gh_delivery and is_duplicate(delivery_key(gh_delivery)):
        py_logger.info("Duplicate webhook delivery %s — skipping", gh_delivery)
        return {"message": "Duplicate delivery, already processed"}

    event = request.headers.get("X-GitHub-Event", "")
    payload = await request.json()

    # ── Pull Request events ───────────────────────────────────────────
    if event == "pull_request":
        action = payload.get("action", "")
        if action not in ("opened", "synchronize", "reopened"):
            return {"message": f"Ignored PR action: {action}"}

        pr = payload["pull_request"]
        repo_full_name = payload["repository"]["full_name"]
        pr_number = pr["number"]
        head_sha = pr["head"]["sha"]

        if is_duplicate(pr_key(repo_full_name, pr_number, head_sha)):
            py_logger.info("Duplicate PR event %s #%s @ %s — skipping", repo_full_name, pr_number, head_sha[:8])
            return {"message": "Already processed this PR at this commit"}

        py_logger.info("Accepted PR #%s on %s (action=%s) — processing in background", pr_number, repo_full_name, action)
        _run_in_background(_process_pr, repo_full_name, pr_number, pr)
        return {"message": "Accepted, processing in background", "pr": pr_number}

    # ── Workflow Run events (pipeline monitoring) ─────────────────────
    if event == "workflow_run":
        action = payload.get("action", "")
        run = payload.get("workflow_run", {})
        conclusion = run.get("conclusion", "")

        # Deployment gate: intercept completed successful workflow runs on main/master
        if action == "completed" and conclusion == "success":
            repo_full_name = payload["repository"]["full_name"]
            branch = run.get("head_branch", "")
            if branch in ("main", "master", "production"):
                run_id = run.get("id", 0)
                if is_duplicate(deploy_key(repo_full_name, run_id)):
                    py_logger.info("Duplicate deployment gate event %s run %s — skipping", repo_full_name, run_id)
                    return {"message": "Already evaluated this deployment"}

                py_logger.info("Accepted deployment gate for %s run %s — processing in background", repo_full_name, run_id)
                _run_in_background(_process_deployment_gate, repo_full_name, run)
                return {"message": "Accepted, evaluating deployment gate in background", "run_id": run_id}

        if action != "completed" or conclusion != "failure":
            return {"message": f"Ignored workflow_run action={action} conclusion={conclusion}"}

        repo_full_name = payload["repository"]["full_name"]
        run_id = run.get("id")

        if is_duplicate(pipeline_key(repo_full_name, run_id)):
            py_logger.info("Duplicate pipeline event %s run %s — skipping", repo_full_name, run_id)
            return {"message": "Already processed this pipeline failure"}

        py_logger.info("Accepted pipeline failure %s run %s — processing in background", repo_full_name, run_id)
        _run_in_background(_process_pipeline, repo_full_name, run)
        return {"message": "Accepted, processing pipeline failure in background", "run_id": run_id}

    # ── Deployment events ─────────────────────────────────────────────
    if event == "deployment":
        repo_full_name = payload["repository"]["full_name"]
        deployment = payload.get("deployment", {})
        sender = payload.get("sender", {}).get("login", "unknown")
        dep_id = deployment.get("id", 0)

        if is_duplicate(deploy_key(repo_full_name, dep_id)):
            py_logger.info("Duplicate deployment event %s id %s — skipping", repo_full_name, dep_id)
            return {"message": "Already evaluated this deployment"}

        py_logger.info("Accepted deployment event %s — processing in background", repo_full_name)
        _run_in_background(_process_deployment_event, repo_full_name, deployment, sender)
        return {"message": "Accepted, evaluating deployment in background"}

    return {"message": f"Ignored event: {event}"}
