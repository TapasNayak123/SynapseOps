"""Poll GitHub for new/updated PRs and trigger the multi-agent pipeline."""

from __future__ import annotations

import logging
import time
import threading

import requests

from config import GITHUB_TOKEN
from github_client import get_pr_details, get_pr_diff, get_pr_files, post_pr_comment
from agents import supervisor, check_and_generate_description
from conflict_detector import check_conflicts
from activity_log import activity_log

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

# Track which PRs we've already processed (repo:pr_number:sha)
_processed: set[str] = set()


def get_open_prs(repo: str) -> list:
    """Fetch all open PRs for a repo."""
    url = f"{_GITHUB_API}/repos/{repo}/pulls?state=open&sort=updated&direction=desc"
    resp = requests.get(url, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def process_pr(repo: str, pr: dict):
    """Run the multi-agent pipeline on a single PR."""
    pr_number = pr["number"]
    head_sha = pr["head"]["sha"]
    key = f"{repo}:{pr_number}:{head_sha}"

    if key in _processed:
        return False

    logger.info(">>> New/updated PR detected: %s #%s — %s", repo, pr_number, pr["title"])
    logger.info("    Head SHA: %s", head_sha)
    activity_log.emit("Poller", "started", f"New PR detected: #{pr_number} — {pr['title']}", repo=repo, pr_number=pr_number)

    try:
        pr_details = get_pr_details(repo, pr_number)
        diff = get_pr_diff(repo, pr_number)
        files = get_pr_files(repo, pr_number)

        # Auto-generate description if empty
        check_and_generate_description(pr_details, diff, files, repo, pr_number)

        # Conflict detection against other open PRs
        check_conflicts(repo, pr_number, files,
                        pr_title=pr.get("title", ""),
                        pr_author=pr.get("user", {}).get("login", ""))

        logger.info("    Fetched %d changed files, running agents...", len(files))

        summary = supervisor(pr_details, diff, files, repo, pr_number)

        post_pr_comment(repo, pr_number, summary)
        logger.info("    ✅ Posted AI summary on PR #%s", pr_number)

        _processed.add(key)
        return True

    except Exception:
        logger.exception("    ❌ Failed to process PR #%s on %s", pr_number, repo)
        return False


def poll_repos(repos: list, interval: int = 60):
    """Continuously poll repos for new/updated PRs."""
    logger.info("=== Poller started for repos: %s (every %ds) ===", repos, interval)

    while True:
        for repo in repos:
            try:
                logger.info("Polling %s for open PRs...", repo)
                prs = get_open_prs(repo)
                logger.info("Found %d open PR(s) in %s", len(prs), repo)

                for pr in prs:
                    process_pr(repo, pr)

            except Exception:
                logger.exception("Error polling %s", repo)

        logger.info("Sleeping %ds until next poll...", interval)
        time.sleep(interval)


def start_poller(repos: list, interval: int = 60):
    """Start the poller in a background thread."""
    thread = threading.Thread(target=poll_repos, args=(repos, interval), daemon=True)
    thread.start()
    logger.info("Poller thread started")
    return thread
