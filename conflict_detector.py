"""Detect file-level conflicts between open PRs and notify via Teams."""

from __future__ import annotations

import logging

from config import TEAMS_WEBHOOK_URL, APP_BASE_URL
from github_client import get_pr_files, post_pr_comment, gh_headers, GITHUB_API, _get_session
from activity_log import activity_log
from app.services.notifier import _get_http, _WEBHOOK_RETRYABLE
from app.services.retry import retry_with_backoff

logger = logging.getLogger(__name__)


def _get_open_prs(repo: str) -> list[dict]:
    """Fetch all open PRs (lightweight list)."""
    url = f"{GITHUB_API}/repos/{repo}/pulls?state=open&per_page=50"
    resp = _get_session().get(url, headers=gh_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def detect_conflicts(repo: str, pr_number: int, pr_files: list[dict]) -> list[dict]:
    """Compare files in `pr_number` against every other open PR.

    Returns a list of conflict dicts:
        {other_pr, other_title, other_author, overlapping_files}
    """
    current_filenames = {f["filename"] for f in pr_files}
    if not current_filenames:
        return []

    open_prs = _get_open_prs(repo)
    conflicts = []

    for other in open_prs:
        if other["number"] == pr_number:
            continue

        try:
            other_files = get_pr_files(repo, other["number"])
            other_filenames = {f["filename"] for f in other_files}
            overlap = current_filenames & other_filenames

            if overlap:
                conflicts.append({
                    "other_pr": other["number"],
                    "other_title": other.get("title", ""),
                    "other_author": other.get("user", {}).get("login", ""),
                    "other_branch": other.get("head", {}).get("ref", ""),
                    "overlapping_files": sorted(overlap),
                })
        except Exception:
            logger.warning("Could not fetch files for PR #%s", other["number"])

    return conflicts


def _build_conflict_comment(repo: str, pr_number: int, conflicts: list[dict]) -> str:
    """Build a Markdown comment listing conflicting PRs."""
    lines = [
        "## ⚠️ Potential Conflict Detected",
        "",
        f"This PR touches files that are also modified in **{len(conflicts)}** other open PR(s):",
        "",
    ]
    for c in conflicts:
        files_str = ", ".join(f"`{f}`" for f in c["overlapping_files"][:10])
        extra = f" (+{len(c['overlapping_files']) - 10} more)" if len(c["overlapping_files"]) > 10 else ""
        lines.append(
            f"- **#{c['other_pr']}** _{c['other_title']}_ by @{c['other_author']} "
            f"— **{len(c['overlapping_files'])} shared file(s)**: {files_str}{extra}"
        )
    lines += [
        "",
        "Please coordinate with the authors above to avoid merge conflicts.",
        "",
        "_🤖 Detected by SynapseOps Conflict Detection Agent_",
    ]
    return "\n".join(lines)


def _send_conflict_teams_notification(
    repo: str, pr_number: int, pr_title: str, pr_author: str, conflicts: list[dict]
):
    """Send a Teams card about the detected conflicts."""
    if not TEAMS_WEBHOOK_URL:
        return

    total_files = sum(len(c["overlapping_files"]) for c in conflicts)
    conflict_lines = []
    for c in conflicts:
        files_preview = ", ".join(c["overlapping_files"][:5])
        conflict_lines.append(
            f"• PR #{c['other_pr']} ({c['other_author']}) — "
            f"{len(c['overlapping_files'])} file(s): {files_preview}"
        )
    conflict_text = "\n".join(conflict_lines)

    pr_url = f"https://github.com/{repo}/pull/{pr_number}"

    payload = {
        "type": "message",
        "attachments": [{
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
                        "items": [{
                            "type": "TextBlock",
                            "text": "⚠️ PR Conflict Detected",
                            "size": "large",
                            "weight": "bolder",
                            "color": "attention",
                        }],
                    },
                    {
                        "type": "FactSet",
                        "facts": [
                            {"title": "📦 Repo", "value": repo},
                            {"title": "🔀 PR", "value": f"#{pr_number} — {pr_title}"},
                            {"title": "👤 Author", "value": pr_author},
                            {"title": "⚠️ Conflicting PRs", "value": str(len(conflicts))},
                            {"title": "📁 Overlapping Files", "value": str(total_files)},
                        ],
                    },
                    {
                        "type": "TextBlock",
                        "text": "**Conflicts:**",
                        "spacing": "medium",
                        "separator": True,
                    },
                    {
                        "type": "TextBlock",
                        "text": conflict_text[:1500],
                        "wrap": True,
                        "size": "small",
                    },
                ],
                "actions": [
                    {
                        "type": "Action.OpenUrl",
                        "title": "🔗 View PR",
                        "url": pr_url,
                    },
                    {
                        "type": "Action.OpenUrl",
                        "title": "📊 Dashboard",
                        "url": f"{APP_BASE_URL}/",
                    },
                ],
            },
        }],
    }

    try:
        _send_conflict_notification_with_retry(TEAMS_WEBHOOK_URL, payload, pr_number)
    except Exception:
        logger.exception("❌ Failed to send conflict notification")


@retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=15.0, retryable_exceptions=_WEBHOOK_RETRYABLE)
def _send_conflict_notification_with_retry(webhook_url: str, payload: dict, pr_number: int):
    resp = _get_http().post(webhook_url, json=payload, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    logger.info("✅ Conflict notification sent for PR #%s", pr_number)


def check_conflicts(repo: str, pr_number: int, pr_files: list[dict],
                    pr_title: str = "", pr_author: str = "") -> list[dict]:
    """Run conflict detection, comment on the PR, and notify Teams.

    Returns the list of conflicts found (empty if none).
    """
    activity_log.emit("Conflict Detector", "started",
                      f"Checking PR #{pr_number} against other open PRs...",
                      repo=repo, pr_number=pr_number)

    conflicts = detect_conflicts(repo, pr_number, pr_files)

    if not conflicts:
        activity_log.emit("Conflict Detector", "completed",
                          "No file-level conflicts found",
                          repo=repo, pr_number=pr_number)
        return []

    total_files = sum(len(c["overlapping_files"]) for c in conflicts)
    activity_log.emit("Conflict Detector", "completed",
                      f"Found {len(conflicts)} conflicting PR(s) with {total_files} shared file(s)",
                      repo=repo, pr_number=pr_number)

    # Comment on the current PR
    comment = _build_conflict_comment(repo, pr_number, conflicts)
    try:
        post_pr_comment(repo, pr_number, comment)
    except Exception:
        logger.exception("Failed to post conflict comment on PR #%s", pr_number)

    # Notify Teams
    _send_conflict_teams_notification(repo, pr_number, pr_title, pr_author, conflicts)

    return conflicts
