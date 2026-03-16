"""GitHub API client for fetching PR data and posting comments."""

from __future__ import annotations

import logging
import threading
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config import GITHUB_TOKEN

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"

_session = None
_session_lock = threading.Lock()


def _get_session() -> requests.Session:
    """Singleton requests session with retry and connection pooling."""
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                s = requests.Session()
                retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[502, 503, 504])
                adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
                s.mount("https://", adapter)
                _session = s
    return _session


def _headers() -> dict:
    """Build auth headers. Lazy so GITHUB_TOKEN can be set after import."""
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }


# Alias so other modules can import a single shared helper
gh_headers = _headers


def get_pr_details(repo_full_name: str, pr_number: int) -> dict:
    """Fetch PR metadata (title, body, author, branch info)."""
    url = f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}"
    resp = _get_session().get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_pr_diff(repo_full_name: str, pr_number: int) -> str:
    """Fetch the raw diff of a pull request."""
    url = f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}"
    hdrs = _headers()
    hdrs["Accept"] = "application/vnd.github.v3.diff"
    resp = _get_session().get(url, headers=hdrs, timeout=60)
    resp.raise_for_status()
    return resp.text


def get_pr_files(repo_full_name: str, pr_number: int) -> list[dict]:
    """Fetch list of changed files with stats."""
    url = f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}/files"
    resp = _get_session().get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def post_pr_comment(repo_full_name: str, pr_number: int, body: str) -> dict:
    """Post a comment on the pull request."""
    url = f"{GITHUB_API}/repos/{repo_full_name}/issues/{pr_number}/comments"
    resp = _get_session().post(url, headers=_headers(), json={"body": body}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def merge_pr(repo_full_name: str, pr_number: int, commit_title: str = None) -> dict:
    """Merge a pull request."""
    url = f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}/merge"
    payload = {"merge_method": "squash"}
    if commit_title:
        payload["commit_title"] = commit_title
    resp = _get_session().put(url, headers=_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def update_pr_body(repo_full_name: str, pr_number: int, body: str) -> dict:
    """Update the body/description of a pull request."""
    url = f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}"
    resp = _get_session().patch(url, headers=_headers(), json={"body": body}, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ── Auto-heal: file and workflow functions ────────────────────────────────

def get_file_content(repo: str, path: str, branch: str) -> dict:
    """Get file content and SHA from a branch."""
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    resp = _get_session().get(url, headers=_headers(), params={"ref": branch}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def update_file(repo: str, path: str, content_b64: str, message: str, branch: str, file_sha: str) -> dict:
    """Update a file on a branch (content must be base64 encoded)."""
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    resp = _get_session().put(url, headers=_headers(), json={
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
    resp = _get_session().put(url, headers=_headers(), json={
        "message": message,
        "content": content_b64,
        "branch": branch,
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()


def rerun_workflow(repo: str, run_id: int) -> bool:
    """Re-run a failed workflow run."""
    url = f"{GITHUB_API}/repos/{repo}/actions/runs/{run_id}/rerun-failed-jobs"
    resp = _get_session().post(url, headers=_headers(), timeout=30)
    return resp.status_code == 201
