"""SynapseOps — Unified application (FastAPI).

Combines the PR analysis dashboard, GitHub webhook receiver, API monitoring,
chat engine, and auto-fix services into a single server.
"""
from contextlib import asynccontextmanager
from pathlib import Path
import hashlib
import hmac
import logging

from fastapi import FastAPI, Request, Form, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import structlog

from app.config import get_settings
from app.routes import metrics, chat, alerts
from app.tasks.scheduler import start_scheduler, stop_scheduler

# Root-level imports (PR analysis pipeline)
from config import GITHUB_WEBHOOK_SECRET, GITHUB_REPOS, POLL_INTERVAL
from github_client import get_pr_details, get_pr_diff, get_pr_files, post_pr_comment, merge_pr
from agents import supervisor, check_and_generate_description
from conflict_detector import check_conflicts
from store import pr_store, pipeline_store
from poller import start_poller
from pipeline_monitor import start_pipeline_monitor
from activity_log import activity_log

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
    _seed_monitored_apis()

    # Start APScheduler (monitoring jobs)
    try:
        start_scheduler()
    except Exception as e:
        logger.warning("scheduler_start_failed", error=str(e))

    # Start PR poller + pipeline monitor threads
    if GITHUB_REPOS:
        py_logger.info("Watching repos: %s (polling every %ds)", GITHUB_REPOS, POLL_INTERVAL)
        start_poller(GITHUB_REPOS, POLL_INTERVAL)
        start_pipeline_monitor(GITHUB_REPOS, POLL_INTERVAL)
    else:
        py_logger.info("No GITHUB_REPO configured — poller disabled.")

    yield

    try:
        stop_scheduler()
    except Exception:
        pass
    logger.info("stopped")


app = FastAPI(title="SynapseOps", version="1.0.0", lifespan=lifespan)

# Include FastAPI routers (monitoring, chat, alerts)
app.include_router(metrics.router)
app.include_router(chat.router)
app.include_router(alerts.router)

# Static files
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


# ── Chat UI ───────────────────────────────────────────────────────────────

@app.get("/chat")
def chat_ui():
    return FileResponse(str(STATIC_DIR / "chat.html"))


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
        pr_details = get_pr_details(repo, pr_num)
        diff = get_pr_diff(repo, pr_num)
        files = get_pr_files(repo, pr_num)

        desc_generated = check_and_generate_description(pr_details, diff, files, repo, pr_num)
        conflicts = check_conflicts(repo, pr_num, files,
                                    pr_title=pr_details.get("title", ""),
                                    pr_author=pr_details.get("user", {}).get("login", ""))
        summary = supervisor(pr_details, diff, files, repo, pr_num)

        posted = False
        if post_comment:
            post_pr_comment(repo, pr_num, summary)
            posted = True

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
    return [
        {
            "repo": r.repo, "pr_number": r.pr_number, "title": r.title,
            "author": r.author, "risk_level": r.risk_level,
            "files_changed": r.files_changed, "total_duration_ms": r.total_duration_ms,
            "timestamp": r.timestamp,
        }
        for r in pr_store.all()
    ]


@app.get("/api/activity")
def api_activity(since: int = Query(0)):
    entries, cursor = activity_log.since(since)
    return {"entries": activity_log.to_dicts(entries), "cursor": cursor}


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

def _verify_signature(payload: bytes, signature: str) -> bool:
    if not GITHUB_WEBHOOK_SECRET:
        py_logger.warning("GITHUB_WEBHOOK_SECRET not set — skipping signature verification")
        return True
    expected = "sha256=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/webhook")
async def webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(body, signature):
        py_logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=403, detail="Invalid signature")

    event = request.headers.get("X-GitHub-Event", "")
    payload = await request.json()

    if event != "pull_request":
        return {"message": f"Ignored event: {event}"}

    action = payload.get("action", "")
    if action not in ("opened", "synchronize", "reopened"):
        return {"message": f"Ignored PR action: {action}"}

    pr = payload["pull_request"]
    repo_full_name = payload["repository"]["full_name"]
    pr_number = pr["number"]

    py_logger.info("Processing PR #%s on %s (action=%s)", pr_number, repo_full_name, action)

    try:
        pr_details = get_pr_details(repo_full_name, pr_number)
        diff = get_pr_diff(repo_full_name, pr_number)
        files = get_pr_files(repo_full_name, pr_number)

        check_and_generate_description(pr_details, diff, files, repo_full_name, pr_number)
        check_conflicts(repo_full_name, pr_number, files,
                        pr_title=pr.get("title", ""),
                        pr_author=pr.get("user", {}).get("login", ""))

        summary = supervisor(pr_details, diff, files, repo_full_name, pr_number)
        post_pr_comment(repo_full_name, pr_number, summary)
        py_logger.info("Posted AI summary on PR #%s", pr_number)
        return {"message": "Summary posted", "pr": pr_number}
    except Exception:
        py_logger.exception("Failed to process PR #%s", pr_number)
        raise HTTPException(status_code=500, detail="Processing failed")
