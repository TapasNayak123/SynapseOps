"""Flask server: GitHub webhook receiver + dashboard UI."""

import hashlib
import hmac
import logging

from flask import Flask, request, jsonify, render_template

from config import GITHUB_WEBHOOK_SECRET, WATCH_REPOS, POLL_INTERVAL
from github_client import get_pr_details, get_pr_diff, get_pr_files, post_pr_comment, merge_pr
from agents import supervisor, check_and_generate_description
from conflict_detector import check_conflicts
from store import pr_store, pipeline_store
from poller import start_poller
from pipeline_monitor import start_pipeline_monitor
from activity_log import activity_log

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)


def verify_signature(payload: bytes, signature: str) -> bool:
    """Verify the GitHub webhook HMAC-SHA256 signature."""
    if not GITHUB_WEBHOOK_SECRET:
        logger.warning("GITHUB_WEBHOOK_SECRET not set — skipping signature verification")
        return True
    expected = "sha256=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ── Dashboard routes ──────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    records = pr_store.all()
    stats = pr_store.stats()
    return render_template("dashboard.html", records=records, stats=stats)


@app.route("/metrics")
def metrics_page():
    metrics = pr_store.metrics()
    return render_template("metrics.html", m=metrics)


@app.route("/api/metrics", methods=["GET"])
def api_metrics():
    return jsonify(pr_store.metrics())


@app.route("/pr/<path:repo>/<int:pr_number>")
def pr_detail(repo, pr_number):
    record = pr_store.get(repo, pr_number)
    if not record:
        return "PR not found", 404
    return render_template("pr_detail.html", pr=record)


@app.route("/test", methods=["GET", "POST"])
def test_pr():
    """Manual test page — enter a repo and PR number to trigger analysis."""
    if request.method == "GET":
        return render_template("test.html", result=None, error=None)

    repo = request.form.get("repo", "").strip()
    pr_number = request.form.get("pr_number", "").strip()

    if not repo or not pr_number:
        return render_template("test.html", result=None, error="Repo and PR number are required.")

    # Accept full GitHub URLs like https://github.com/owner/repo or owner/repo
    repo = repo.rstrip("/")
    if "github.com" in repo:
        # Extract owner/repo from URL
        parts = repo.split("github.com/")[-1].split("/")
        if len(parts) >= 2:
            repo = f"{parts[0]}/{parts[1]}"

    try:
        pr_number = int(pr_number)
        pr_details = get_pr_details(repo, pr_number)
        diff = get_pr_diff(repo, pr_number)
        files = get_pr_files(repo, pr_number)

        # Auto-generate description if empty
        desc_generated = check_and_generate_description(pr_details, diff, files, repo, pr_number)

        # Conflict detection
        conflicts = check_conflicts(repo, pr_number, files,
                                    pr_title=pr_details.get("title", ""),
                                    pr_author=pr_details.get("user", {}).get("login", ""))

        summary = supervisor(pr_details, diff, files, repo, pr_number)

        posted = False
        if request.form.get("post_comment"):
            post_pr_comment(repo, pr_number, summary)
            posted = True

        return render_template("test.html", result={"summary": summary, "posted": posted, "repo": repo, "pr_number": pr_number, "desc_generated": desc_generated, "conflicts": conflicts}, error=None)

    except Exception as e:
        logger.exception("Test failed for %s #%s", repo, pr_number)
        return render_template("test.html", result=None, error=str(e))


# ── API routes ────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/stats", methods=["GET"])
def api_stats():
    return jsonify(pr_store.stats())


@app.route("/api/prs", methods=["GET"])
def api_prs():
    records = pr_store.all()
    return jsonify([
        {
            "repo": r.repo,
            "pr_number": r.pr_number,
            "title": r.title,
            "author": r.author,
            "risk_level": r.risk_level,
            "files_changed": r.files_changed,
            "total_duration_ms": r.total_duration_ms,
            "timestamp": r.timestamp,
        }
        for r in records
    ])


# ── PR Action endpoints (called from Teams cards) ────────────────────────

@app.route("/action/approve/<path:repo>/<int:pr_number>", methods=["GET", "POST"])
def action_approve(repo, pr_number):
    """Approval page — GET shows confirmation, POST merges the PR."""
    if request.method == "GET":
        return render_template("action.html",
            action_type="approve", action_title="Approve & Merge PR",
            action_emoji="✅", repo=repo, pr_number=pr_number,
            result=None, success=None)

    try:
        merge_pr(repo, pr_number, commit_title=f"Approved and merged via AI Agent (PR #{pr_number})")
        post_pr_comment(repo, pr_number, "✅ **Approved and merged** via AI PR Summary Agent from Microsoft Teams.")
        logger.info("PR #%s on %s merged via Teams approval", pr_number, repo)
        return render_template("action.html",
            action_type="approve", action_title="Approve & Merge PR",
            action_emoji="✅", repo=repo, pr_number=pr_number,
            result=f"PR #{pr_number} merged successfully!", success=True)
    except Exception as e:
        logger.exception("Failed to merge PR #%s", pr_number)
        return render_template("action.html",
            action_type="approve", action_title="Approve & Merge PR",
            action_emoji="✅", repo=repo, pr_number=pr_number,
            result=f"Failed to merge: {e}", success=False)


@app.route("/action/reject/<path:repo>/<int:pr_number>", methods=["GET", "POST"])
def action_reject(repo, pr_number):
    """Reject page — GET shows form, POST posts changes-requested comment."""
    if request.method == "GET":
        return render_template("action.html",
            action_type="reject", action_title="Request Changes",
            action_emoji="🔴", repo=repo, pr_number=pr_number,
            result=None, success=None)

    reason = request.form.get("reason", "").strip() or "Changes requested by reviewer via AI PR Summary Agent."
    try:
        post_pr_comment(repo, pr_number, f"🔴 **Changes Requested** (via Teams)\n\n{reason}")
        logger.info("Changes requested on PR #%s on %s via Teams", pr_number, repo)
        return render_template("action.html",
            action_type="reject", action_title="Request Changes",
            action_emoji="🔴", repo=repo, pr_number=pr_number,
            result=f"Changes requested on PR #{pr_number}.", success=True)
    except Exception as e:
        logger.exception("Failed to request changes on PR #%s", pr_number)
        return render_template("action.html",
            action_type="reject", action_title="Request Changes",
            action_emoji="🔴", repo=repo, pr_number=pr_number,
            result=f"Failed: {e}", success=False)


@app.route("/api/pr/approve", methods=["POST"])
def api_approve_and_merge():
    """Approve and merge a PR — triggered from Teams card."""
    data = request.json or {}
    repo = data.get("repo", "")
    pr_number = data.get("pr_number")

    if not repo or not pr_number:
        return jsonify({"error": "repo and pr_number required"}), 400

    try:
        pr_number = int(pr_number)
        result = merge_pr(repo, pr_number, commit_title=f"Approved and merged via AI Agent (PR #{pr_number})")
        post_pr_comment(repo, pr_number, "✅ **Approved and merged** via AI PR Summary Agent from Microsoft Teams.")
        logger.info("PR #%s on %s merged via Teams approval", pr_number, repo)
        return jsonify({"message": f"PR #{pr_number} merged successfully", "sha": result.get("sha", "")}), 200
    except Exception as e:
        logger.exception("Failed to merge PR #%s on %s", pr_number, repo)
        return jsonify({"error": str(e)}), 500


@app.route("/api/pr/reject", methods=["POST"])
def reject_pr():
    """Request changes on a PR — triggered from Teams card."""
    data = request.json or {}
    repo = data.get("repo", "")
    pr_number = data.get("pr_number")
    reason = data.get("reason", "Changes requested by reviewer via AI PR Summary Agent.")

    if not repo or not pr_number:
        return jsonify({"error": "repo and pr_number required"}), 400

    try:
        pr_number = int(pr_number)
        post_pr_comment(repo, pr_number, f"🔴 **Changes Requested** (via Teams)\n\n{reason}")
        logger.info("Changes requested on PR #%s on %s via Teams", pr_number, repo)
        return jsonify({"message": f"Changes requested on PR #{pr_number}"}), 200
    except Exception as e:
        logger.exception("Failed to request changes on PR #%s on %s", pr_number, repo)
        return jsonify({"error": str(e)}), 500


# ── Activity Log routes ───────────────────────────────────────────────────

@app.route("/activity")
def activity_page():
    entries = activity_log.all()
    return render_template("activity.html", entries=entries)


@app.route("/api/activity", methods=["GET"])
def api_activity():
    since = request.args.get("since", 0, type=int)
    entries, cursor = activity_log.since(since)
    return jsonify({"entries": activity_log.to_dicts(entries), "cursor": cursor})


# ── Webhook ───────────────────────────────────────────────────────────────

@app.route("/pipelines")
def pipelines_dashboard():
    records = pipeline_store.all()
    stats = pipeline_store.stats()
    return render_template("pipelines.html", records=records, stats=stats)


@app.route("/pipeline/<path:repo>/<int:run_id>")
def pipeline_detail(repo, run_id):
    record = pipeline_store.get(repo, run_id)
    if not record:
        return "Pipeline run not found", 404
    return render_template("pipeline_detail.html", p=record)


@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(request.data, signature):
        logger.warning("Invalid webhook signature")
        return jsonify({"error": "Invalid signature"}), 403

    event = request.headers.get("X-GitHub-Event", "")
    payload = request.json

    if event != "pull_request":
        return jsonify({"message": f"Ignored event: {event}"}), 200

    action = payload.get("action", "")
    if action not in ("opened", "synchronize", "reopened"):
        return jsonify({"message": f"Ignored PR action: {action}"}), 200

    pr = payload["pull_request"]
    repo_full_name = payload["repository"]["full_name"]
    pr_number = pr["number"]

    logger.info("Processing PR #%s on %s (action=%s)", pr_number, repo_full_name, action)

    try:
        pr_details = get_pr_details(repo_full_name, pr_number)
        diff = get_pr_diff(repo_full_name, pr_number)
        files = get_pr_files(repo_full_name, pr_number)

        # Auto-generate description if empty
        check_and_generate_description(pr_details, diff, files, repo_full_name, pr_number)

        # Conflict detection
        check_conflicts(repo_full_name, pr_number, files,
                        pr_title=pr.get("title", ""),
                        pr_author=pr.get("user", {}).get("login", ""))

        summary = supervisor(pr_details, diff, files, repo_full_name, pr_number)

        post_pr_comment(repo_full_name, pr_number, summary)
        logger.info("Posted AI summary on PR #%s", pr_number)

        return jsonify({"message": "Summary posted", "pr": pr_number}), 200

    except Exception:
        logger.exception("Failed to process PR #%s", pr_number)
        return jsonify({"error": "Processing failed"}), 500


if __name__ == "__main__":
    # Start background poller if repos are configured
    if WATCH_REPOS:
        logger.info("Watching repos: %s (polling every %ds)", WATCH_REPOS, POLL_INTERVAL)
        start_poller(WATCH_REPOS, POLL_INTERVAL)
        start_pipeline_monitor(WATCH_REPOS, POLL_INTERVAL)
    else:
        logger.info("No WATCH_REPOS configured — poller disabled. Set WATCH_REPOS in .env to enable.")

    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
