"""
Auto-fix engine: categorizes bugs, fetches source code from GitHub,
generates fixes via Bedrock LLM, and creates PRs for approved fixes.
"""
import json
import httpx
import base64
import structlog
from datetime import datetime
from app.config import get_settings
from app.services.llm import LLMService
from app.services.dynamodb import DynamoDBService
from app.services.notifier import NotifierService
from app.services.code_analyzer import CodeAnalyzer, AUTO_FIXABLE_CATEGORIES, BugCategory

logger = structlog.get_logger()


class AutoFixService:
    def __init__(self):
        self.llm = LLMService()
        self.db = DynamoDBService()
        self.notifier = NotifierService()
        self.code_analyzer = CodeAnalyzer()
        self.settings = get_settings()

    def analyze_and_fix(self, error_message: str, stack_trace: str = "") -> dict:
        """
        Full auto-fix pipeline:
        1. Categorize the bug (rule-based)
        2. Parse stack trace to find source file + line
        3. Fetch actual code from GitHub
        4. Send code + error to LLM for fix generation
        5. Create PR if confidence is high enough
        """
        # Step 1: Categorize
        category = self.code_analyzer.categorize_error(error_message, stack_trace)

        result = {
            "error_message": error_message,
            "category": category,
            "stack_frames": [],
            "source_code": None,
            "llm_analysis": None,
            "fix_generated": False,
            "pr_created": False,
            "pr_url": None,
        }

        # Step 2: Parse stack trace
        frames = self.code_analyzer.parse_stack_trace(stack_trace)
        result["stack_frames"] = frames

        if not frames:
            result["llm_analysis"] = self.llm.analyze_error(error_message, stack_trace)
            self._store_audit(result)
            return result

        # Step 3: Fetch source code from GitHub for the top frame
        top_frame = frames[0]
        repo_path = self.code_analyzer.extract_repo_path(top_frame["file"])
        source_file = self.code_analyzer.fetch_file_from_github(repo_path)

        if not source_file:
            result["llm_analysis"] = self.llm.analyze_error(error_message, stack_trace)
            self._store_audit(result)
            return result

        # Get code context around the error line
        code_context = self.code_analyzer.get_code_context(
            source_file["content"], top_frame["line"]
        )
        result["source_code"] = {
            "file_path": repo_path,
            "error_line": top_frame["line"],
            "snippet": code_context["code_snippet"],
            "github_url": source_file["url"],
        }

        # Step 4: Send real code to LLM for analysis
        llm_result = self._analyze_with_code(
            error_message, stack_trace, repo_path,
            source_file["content"], code_context, category
        )
        result["llm_analysis"] = llm_result

        # Step 5: Create PR if auto-fixable and high confidence
        if (
            category["auto_fixable"]
            and llm_result.get("confidence", 0) >= 0.8
            and llm_result.get("fixed_code")
        ):
            result["fix_generated"] = True
            pr = self._create_fix_pr(
                repo_path, source_file, llm_result, error_message, category
            )
            if pr:
                result["pr_created"] = True
                result["pr_url"] = pr.get("html_url")

                self.notifier.send_teams_alert({
                    "api_path": repo_path,
                    "alert_type": "auto_fix_pr_created",
                    "error_rate": 0,
                    "threshold": 0,
                    "total_requests": 0,
                    "error_count": 0,
                    "timestamp": datetime.utcnow().isoformat(),
                    "extra": f"PR: {pr.get('html_url', 'N/A')} | Fix: {llm_result.get('explanation', '')[:100]}",
                })

        self._store_audit(result)
        return result

    def _analyze_with_code(
        self, error_message: str, stack_trace: str,
        file_path: str, full_content: str,
        code_context: dict, category: dict
    ) -> dict:
        """Send actual source code + error to LLM for precise fix generation."""
        prompt = f"""You are a senior Node.js engineer. Analyze this production error and generate a fix.

ERROR: {error_message}

STACK TRACE:
{stack_trace}

BUG CATEGORY: {category['category']}
AUTO-FIXABLE: {category['auto_fixable']}

FILE: {file_path}
CODE AROUND ERROR (line {code_context['error_line']}):
```javascript
{code_context['code_snippet']}
```

FULL FILE CONTENT:
```javascript
{full_content[:8000]}
```

INSTRUCTIONS:
1. Identify the exact root cause
2. Generate the COMPLETE fixed file content (not just a snippet)
3. Only fix the specific bug — do NOT refactor or change unrelated code
4. Rate your confidence (0.0 to 1.0) — only rate >= 0.8 if you are certain

Respond in JSON:
{{
    "root_cause": "...",
    "explanation": "...",
    "confidence": 0.0,
    "fixed_code": "...complete fixed file content...",
    "changes_summary": "one-line description of what changed"
}}"""

        try:
            response = self.llm.invoke(prompt, max_tokens=4096)
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "root_cause": "LLM response parse failed",
                "explanation": response[:500] if response else "",
                "confidence": 0.0,
                "fixed_code": None,
                "changes_summary": None,
            }
        except Exception as e:
            logger.error("llm_code_analysis_failed", error=str(e))
            return {"root_cause": str(e), "confidence": 0.0, "fixed_code": None}

    def _create_fix_pr(
        self, file_path: str, source_file: dict,
        llm_result: dict, error_message: str, category: dict
    ) -> dict | None:
        """Create a GitHub PR with the fix."""
        if not self.settings.github_token or not self.settings.github_repo:
            logger.warning("github_not_configured_for_pr")
            return None

        repo = self.settings.github_repo
        token = self.settings.github_token
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        base_url = f"https://api.github.com/repos/{repo}"

        try:
            branch_name = f"synapse-ops/auto-fix/{category['category']}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

            with httpx.Client(timeout=20) as client:
                # 1. Get default branch SHA
                resp = client.get(f"{base_url}/git/ref/heads/main", headers=headers)
                resp.raise_for_status()
                base_sha = resp.json()["object"]["sha"]

                # 2. Create branch
                client.post(
                    f"{base_url}/git/refs",
                    headers=headers,
                    json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
                ).raise_for_status()

                # 3. Update file on the new branch
                encoded = base64.b64encode(llm_result["fixed_code"].encode()).decode()
                commit_msg = f"fix({category['category']}): {llm_result.get('changes_summary', 'auto-fix')}\n\nError: {error_message[:200]}\nGenerated by SynapseOps Agent"

                client.put(
                    f"{base_url}/contents/{file_path}",
                    headers=headers,
                    json={
                        "message": commit_msg,
                        "content": encoded,
                        "sha": source_file["sha"],
                        "branch": branch_name,
                    },
                ).raise_for_status()

                # 4. Create PR
                pr_body = f"""## 🤖 SynapseOps Auto-Fix

**Error:** `{error_message[:300]}`
**Category:** `{category['category']}`
**Confidence:** `{llm_result.get('confidence', 0)}`
**File:** `{file_path}`

### Root Cause
{llm_result.get('root_cause', 'N/A')}

### Changes
{llm_result.get('changes_summary', 'N/A')}

### Explanation
{llm_result.get('explanation', 'N/A')}

---
> ⚠️ This PR was auto-generated by SynapseOps. Please review before merging."""

                pr_resp = client.post(
                    f"{base_url}/pulls",
                    headers=headers,
                    json={
                        "title": f"[SynapseOps] fix({category['category']}): {llm_result.get('changes_summary', 'auto-fix')[:80]}",
                        "body": pr_body,
                        "head": branch_name,
                        "base": "main",
                    },
                )
                pr_resp.raise_for_status()
                pr_data = pr_resp.json()

                logger.info("auto_fix_pr_created", pr_url=pr_data["html_url"], file=file_path)
                return pr_data

        except Exception as e:
            logger.error("auto_fix_pr_creation_failed", error=str(e), file=file_path)
            return None

    def _store_audit(self, result: dict) -> None:
        """Store auto-fix attempt in audit trail."""
        self.db.store_audit_log({
            "action": "auto_fix_analysis",
            "error_message": result.get("error_message", ""),
            "category": result.get("category", {}).get("category", "unknown"),
            "auto_fixable": result.get("category", {}).get("auto_fixable", False),
            "fix_generated": result.get("fix_generated", False),
            "pr_created": result.get("pr_created", False),
            "pr_url": result.get("pr_url"),
            "confidence": result.get("llm_analysis", {}).get("confidence", 0),
            "timestamp": datetime.utcnow().isoformat(),
        })

    def get_fix_history(self, limit: int = 20) -> list[dict]:
        """Get history of auto-fix attempts."""
        return self.db.get_audit_logs(action="auto_fix_analysis", limit=limit)
