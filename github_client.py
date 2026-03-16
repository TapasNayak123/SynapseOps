"""GitHub API client for fetching PR data and posting comments."""

from __future__ import annotations

import requests
from config import GITHUB_TOKEN

GITHUB_API = "https://api.github.com"
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}


def get_pr_details(repo_full_name: str, pr_number: int) -> dict:
    """Fetch PR metadata (title, body, author, branch info)."""
    url = f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_pr_diff(repo_full_name: str, pr_number: int) -> str:
    """Fetch the raw diff of a pull request."""
    url = f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}"
    diff_headers = {**HEADERS, "Accept": "application/vnd.github.v3.diff"}
    resp = requests.get(url, headers=diff_headers, timeout=60)
    resp.raise_for_status()
    return resp.text


def get_pr_files(repo_full_name: str, pr_number: int) -> list[dict]:
    """Fetch list of changed files with stats."""
    url = f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}/files"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def post_pr_comment(repo_full_name: str, pr_number: int, body: str) -> dict:
    """Post a comment on the pull request."""
    url = f"{GITHUB_API}/repos/{repo_full_name}/issues/{pr_number}/comments"
    resp = requests.post(url, headers=HEADERS, json={"body": body}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def merge_pr(repo_full_name: str, pr_number: int, commit_title: str = None) -> dict:
    """Merge a pull request."""
    url = f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}/merge"
    body = {"merge_method": "squash"}
    if commit_title:
        body["commit_title"] = commit_title
    resp = requests.put(url, headers=HEADERS, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


def update_pr_body(repo_full_name: str, pr_number: int, body: str) -> dict:
    """Update the body/description of a pull request."""
    url = f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}"
    resp = requests.patch(url, headers=HEADERS, json={"body": body}, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ── Auto-heal: file and workflow functions ────────────────────────────────

def get_file_content(repo: str, path: str, branch: str) -> dict:
    """Get file content and SHA from a branch."""
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}?ref={branch}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def update_file(repo: str, path: str, content_b64: str, message: str, branch: str, file_sha: str) -> dict:
    """Update a file on a branch (content must be base64 encoded)."""
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    resp = requests.put(url, headers=HEADERS, json={
        "message": message,
        "content": content_b64,
        "sha": file_sha,
        "branch": branch,
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()


def create_file(repo: str, path: str, content_b64: str, message: str, branch: str) -> dict:
    """Create a new file on a branch (content must be base64 encoded)."""
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    resp = requests.put(url, headers=HEADERS, json={
        "message": message,
        "content": content_b64,
        "branch": branch,
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()


def rerun_workflow(repo: str, run_id: int) -> bool:
    """Re-run a failed workflow run."""
    url = f"{GITHUB_API}/repos/{repo}/actions/runs/{run_id}/rerun-failed-jobs"
    resp = requests.post(url, headers=HEADERS, timeout=30)
    return resp.status_code == 201
