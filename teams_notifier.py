"""Send PR summary notifications to Microsoft Teams via webhook (Workflows)."""

from __future__ import annotations

import logging
import requests
from config import TEAMS_WEBHOOK_URL, APP_BASE_URL

logger = logging.getLogger(__name__)


def send_teams_notification(
    repo: str,
    pr_number: int,
    title: str,
    author: str,
    branch: str,
    target: str,
    risk_level: str,
    pr_type: str,
    priority: str,
    summary: str,
    files_changed: int,
    additions: int,
    deletions: int,
    duration_ms: int,
):
    """Post a PR summary card with approval actions to Teams."""
    if not TEAMS_WEBHOOK_URL:
        logger.warning("TEAMS_WEBHOOK_URL not set — skipping Teams notification")
        return

    pr_url = f"https://github.com/{repo}/pull/{pr_number}"
    risk_emoji = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(risk_level, "⚪")

    # Build approval/reject URLs
    approve_url = f"{APP_BASE_URL}/action/approve/{repo}/{pr_number}"
    reject_url = f"{APP_BASE_URL}/action/reject/{repo}/{pr_number}"

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
                            "style": "emphasis",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": f"🤖 AI PR Summary: #{pr_number}",
                                    "size": "large",
                                    "weight": "bolder",
                                    "color": "accent",
                                },
                                {
                                    "type": "TextBlock",
                                    "text": title,
                                    "size": "medium",
                                    "weight": "bolder",
                                    "wrap": True,
                                },
                            ],
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "👤 Author", "value": author},
                                {"title": "🏷️ Type", "value": pr_type},
                                {"title": "🎯 Priority", "value": priority},
                                {"title": "🔀 Branch", "value": f"{branch} → {target}"},
                                {"title": "📁 Files", "value": f"{files_changed} (+{additions} -{deletions})"},
                                {"title": f"{risk_emoji} Risk", "value": risk_level},
                                {"title": "⏱️ Time", "value": f"{duration_ms / 1000:.1f}s"},
                                {"title": "📦 Repo", "value": repo},
                            ],
                        },
                        {
                            "type": "TextBlock",
                            "text": "**AI Summary**",
                            "spacing": "medium",
                            "separator": True,
                        },
                        {
                            "type": "TextBlock",
                            "text": summary[:2000],
                            "wrap": True,
                            "size": "small",
                        },
                        {
                            "type": "Container",
                            "separator": True,
                            "spacing": "medium",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": "**🔐 Reviewer Action Required**",
                                    "weight": "bolder",
                                },
                                {
                                    "type": "TextBlock",
                                    "text": "Approve to merge this PR or request changes.",
                                    "size": "small",
                                    "color": "light",
                                },
                            ],
                        },
                    ],
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "✅ Approve & Merge",
                            "url": approve_url,
                            "style": "positive",
                        },
                        {
                            "type": "Action.OpenUrl",
                            "title": "🔴 Request Changes",
                            "url": reject_url,
                        },
                        {
                            "type": "Action.OpenUrl",
                            "title": "🔗 View on GitHub",
                            "url": pr_url,
                        },
                    ],
                },
            }
        ],
    }

    try:
        resp = requests.post(
            TEAMS_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        logger.info("✅ Teams notification sent for PR #%s", pr_number)
    except Exception:
        logger.exception("❌ Failed to send Teams notification for PR #%s", pr_number)
