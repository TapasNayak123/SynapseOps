"""
Node.js error categorization and source code fetching from GitHub.
Parses stack traces, classifies bug severity, and fetches actual source code.
"""
import re
import httpx
import base64
import structlog
from enum import Enum
from app.config import get_settings

logger = structlog.get_logger()


class BugCategory(str, Enum):
    # Auto-fixable (small bugs)
    NULL_REFERENCE = "null_reference"          # Cannot read property of undefined/null
    TYPE_ERROR = "type_error"                  # Type mismatch, wrong argument type
    MISSING_IMPORT = "missing_import"          # Module not found, require failed
    UNHANDLED_PROMISE = "unhandled_promise"    # Unhandled promise rejection
    MISSING_NULL_CHECK = "missing_null_check"  # Optional chaining needed
    SYNTAX_ERROR = "syntax_error"              # JSON parse, unexpected token
    ENV_CONFIG = "env_config"                  # Missing env var, config error
    MISSING_AWAIT = "missing_await"            # Forgot await on async call
    WRONG_STATUS_CODE = "wrong_status_code"    # Returning wrong HTTP status
    MISSING_VALIDATION = "missing_validation"  # Input validation missing

    # Needs human review (complex bugs)
    MEMORY_LEAK = "memory_leak"
    RACE_CONDITION = "race_condition"
    DB_CONNECTION = "db_connection"
    AUTH_FAILURE = "auth_failure"
    TIMEOUT = "timeout"
    INFRASTRUCTURE = "infrastructure"
    UNKNOWN = "unknown"


# Categories the agent can auto-fix
AUTO_FIXABLE_CATEGORIES = {
    BugCategory.NULL_REFERENCE,
    BugCategory.TYPE_ERROR,
    BugCategory.MISSING_IMPORT,
    BugCategory.UNHANDLED_PROMISE,
    BugCategory.MISSING_NULL_CHECK,
    BugCategory.SYNTAX_ERROR,
    BugCategory.ENV_CONFIG,
    BugCategory.MISSING_AWAIT,
    BugCategory.WRONG_STATUS_CODE,
    BugCategory.MISSING_VALIDATION,
}


# Rule-based patterns for Node.js error classification
ERROR_PATTERNS = [
    (r"Cannot read propert(y|ies) of (undefined|null)", BugCategory.NULL_REFERENCE),
    (r"TypeError:.*is not a function", BugCategory.TYPE_ERROR),
    (r"TypeError:.*is not (a |an )", BugCategory.TYPE_ERROR),
    (r"Cannot find module", BugCategory.MISSING_IMPORT),
    (r"Module not found", BugCategory.MISSING_IMPORT),
    (r"UnhandledPromiseRejection", BugCategory.UNHANDLED_PROMISE),
    (r"Unhandled promise rejection", BugCategory.UNHANDLED_PROMISE),
    (r"SyntaxError: Unexpected token", BugCategory.SYNTAX_ERROR),
    (r"SyntaxError:.*JSON", BugCategory.SYNTAX_ERROR),
    (r"JSON\.parse", BugCategory.SYNTAX_ERROR),
    (r"(ECONNREFUSED|ENOTFOUND|ETIMEDOUT).*database", BugCategory.DB_CONNECTION),
    (r"(ECONNREFUSED|ENOTFOUND|ETIMEDOUT)", BugCategory.TIMEOUT),
    (r"(heap|memory|allocation failed|out of memory)", BugCategory.MEMORY_LEAK),
    (r"(ENOMEM|JavaScript heap)", BugCategory.MEMORY_LEAK),
    (r"(401|403|Unauthorized|Forbidden|jwt|token expired)", BugCategory.AUTH_FAILURE),
    (r"(missing|undefined|not set).*(env|config|variable|key)", BugCategory.ENV_CONFIG),
    (r"(await|async|Promise).*(?:missing|forgot)", BugCategory.MISSING_AWAIT),
    (r"(SIGTERM|SIGKILL|OOMKilled|CrashLoopBackOff)", BugCategory.INFRASTRUCTURE),
]


class CodeAnalyzer:
    def __init__(self):
        self.settings = get_settings()

    def categorize_error(self, error_message: str, stack_trace: str = "") -> dict:
        """
        Rule-based bug categorization from error message and stack trace.
        Returns category, severity, and whether it's auto-fixable.
        """
        combined = f"{error_message}\n{stack_trace}"

        # Try rule-based matching first
        for pattern, category in ERROR_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                return {
                    "category": category.value,
                    "auto_fixable": category in AUTO_FIXABLE_CATEGORIES,
                    "severity": "low" if category in AUTO_FIXABLE_CATEGORIES else "high",
                    "matched_pattern": pattern,
                }

        return {
            "category": BugCategory.UNKNOWN.value,
            "auto_fixable": False,
            "severity": "medium",
            "matched_pattern": None,
        }

    def parse_stack_trace(self, stack_trace: str) -> list[dict]:
        """
        Parse a Node.js stack trace to extract file paths and line numbers.
        Example: "at UserService.getUser (/app/src/services/user.service.js:45:12)"
        """
        frames = []
        # Node.js stack frame pattern
        pattern = r"at\s+(?:(.+?)\s+)?\(?((?:/[^:)]+|[A-Za-z]:\\[^:)]+)):(\d+):(\d+)\)?"

        for match in re.finditer(pattern, stack_trace):
            func_name = match.group(1) or "anonymous"
            file_path = match.group(2)
            line = int(match.group(3))
            col = int(match.group(4))

            # Skip node_modules and internal frames
            if "node_modules" in file_path or file_path.startswith("node:"):
                continue

            frames.append({
                "function": func_name,
                "file": file_path,
                "line": line,
                "column": col,
            })

        return frames

    def extract_repo_path(self, absolute_path: str) -> str:
        """
        Convert container absolute path to repo-relative path.
        e.g. "/app/src/services/user.service.js" -> "src/services/user.service.js"
        """
        # Common container working dirs
        prefixes = ["/app/", "/usr/src/app/", "/home/node/app/", "/opt/app/"]
        for prefix in prefixes:
            if absolute_path.startswith(prefix):
                return absolute_path[len(prefix):]
        # Fallback: strip leading /
        return absolute_path.lstrip("/")

    def fetch_file_from_github(self, file_path: str, branch: str = "main") -> dict | None:
        """Fetch a source file from the GitHub repo."""
        if not self.settings.github_token or not self.settings.github_repo:
            logger.warning("github_not_configured")
            return None

        url = f"https://api.github.com/repos/{self.settings.github_repo}/contents/{file_path}"
        headers = {
            "Authorization": f"Bearer {self.settings.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        params = {"ref": branch}

        try:
            with httpx.Client() as client:
                resp = client.get(url, headers=headers, params=params, timeout=15)
                if resp.status_code == 404:
                    logger.warning("github_file_not_found", path=file_path)
                    return None
                resp.raise_for_status()

            data = resp.json()
            content = base64.b64decode(data["content"]).decode("utf-8")
            return {
                "path": file_path,
                "content": content,
                "sha": data["sha"],
                "size": data["size"],
                "url": data["html_url"],
            }
        except Exception as e:
            logger.error("github_file_fetch_failed", path=file_path, error=str(e))
            return None

    def get_code_context(self, file_content: str, line_number: int, context_lines: int = 15) -> dict:
        """Extract code around the error line with context."""
        lines = file_content.split("\n")
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)

        return {
            "error_line": line_number,
            "start_line": start + 1,
            "end_line": end,
            "code_snippet": "\n".join(
                f"{i+1:4d} | {line}" for i, line in enumerate(lines[start:end], start=start)
            ),
            "error_line_content": lines[line_number - 1] if line_number <= len(lines) else "",
        }
