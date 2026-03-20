"""Node.js error categorization and GitHub source code fetching."""
from __future__ import annotations

import re
import base64
import structlog
from enum import Enum
from typing import Optional, List, Dict
from app.config import get_settings
from github_client import get_file_content as _gh_get_file

logger = structlog.get_logger()


class BugCategory(str, Enum):
    # Auto-fixable
    NULL_REFERENCE = "null_reference"
    TYPE_ERROR = "type_error"
    MISSING_IMPORT = "missing_import"
    UNHANDLED_PROMISE = "unhandled_promise"
    SYNTAX_ERROR = "syntax_error"
    ENV_CONFIG = "env_config"
    # Needs human review
    MEMORY_LEAK = "memory_leak"
    DB_CONNECTION = "db_connection"
    AUTH_FAILURE = "auth_failure"
    TIMEOUT = "timeout"
    INFRASTRUCTURE = "infrastructure"
    UNKNOWN = "unknown"


AUTO_FIXABLE_CATEGORIES = {BugCategory.NULL_REFERENCE, BugCategory.TYPE_ERROR, BugCategory.MISSING_IMPORT,
                           BugCategory.UNHANDLED_PROMISE, BugCategory.SYNTAX_ERROR, BugCategory.ENV_CONFIG}

ERROR_PATTERNS = [
    (r"Cannot read propert(y|ies) of (undefined|null)", BugCategory.NULL_REFERENCE),
    (r"TypeError:.*is not a function", BugCategory.TYPE_ERROR),
    (r"Cannot find module|Module not found", BugCategory.MISSING_IMPORT),
    (r"UnhandledPromiseRejection|Unhandled promise rejection", BugCategory.UNHANDLED_PROMISE),
    (r"SyntaxError.*JSON|JSON\.parse", BugCategory.SYNTAX_ERROR),
    (r"(ECONNREFUSED|ENOTFOUND|ETIMEDOUT).*database", BugCategory.DB_CONNECTION),
    (r"ECONNREFUSED|ENOTFOUND|ETIMEDOUT", BugCategory.TIMEOUT),
    (r"heap|memory|out of memory|ENOMEM", BugCategory.MEMORY_LEAK),
    (r"\b(401|403)\b|Unauthorized|Forbidden|jwt|token expired", BugCategory.AUTH_FAILURE),
    (r"(missing|undefined|not set).*(env|config|variable)", BugCategory.ENV_CONFIG),
    (r"SIGTERM|SIGKILL|OOMKilled|CrashLoopBackOff", BugCategory.INFRASTRUCTURE),
]


class CodeAnalyzer:
    def __init__(self):
        self.settings = get_settings()

    def categorize_error(self, error_message: str, stack_trace: str = "") -> dict:
        combined = f"{error_message}\n{stack_trace}"
        for pattern, category in ERROR_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                return {"category": category.value, "auto_fixable": category in AUTO_FIXABLE_CATEGORIES,
                        "severity": "low" if category in AUTO_FIXABLE_CATEGORIES else "high"}
        return {"category": BugCategory.UNKNOWN.value, "auto_fixable": False, "severity": "medium"}

    def parse_stack_trace(self, stack_trace: str) -> List[Dict]:
        frames = []
        pattern = r"at\s+(?:(.+?)\s+)?\(?((?:/[^:)]+|[A-Za-z]:\\[^:)]+)):(\d+):(\d+)\)?"
        for m in re.finditer(pattern, stack_trace):
            path = m.group(2)
            if "node_modules" in path or path.startswith("node:"):
                continue
            frames.append({"function": m.group(1) or "anonymous", "file": path,
                           "line": int(m.group(3)), "column": int(m.group(4))})
        return frames

    def extract_repo_path(self, absolute_path: str) -> str:
        for prefix in ["/app/", "/usr/src/app/", "/home/node/app/", "/opt/app/"]:
            if absolute_path.startswith(prefix):
                return absolute_path[len(prefix):]
        return absolute_path.lstrip("/")

    def fetch_file_from_github(self, file_path: str, branch: str = "main") -> Optional[Dict]:
        if not self.settings.github_token or not self.settings.github_repo:
            return None
        try:
            data = _gh_get_file(self.settings.github_repo, file_path, branch)
            return {"path": file_path, "content": base64.b64decode(data["content"]).decode("utf-8"),
                    "sha": data["sha"], "url": data.get("html_url", "")}
        except Exception as e:
            logger.error("github_fetch_failed", path=file_path, error=str(e))
            return None

    def get_code_context(self, content: str, line_number: int, context: int = 15) -> dict:
        lines = content.split("\n")
        start = max(0, line_number - context - 1)
        end = min(len(lines), line_number + context)
        return {"error_line": line_number, "start_line": start + 1, "end_line": end,
                "code_snippet": "\n".join(f"{i+1:4d} | {l}" for i, l in enumerate(lines[start:end], start=start)),
                "error_line_content": lines[line_number - 1] if line_number <= len(lines) else ""}
