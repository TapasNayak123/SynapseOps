"""Multi-agent system: Diff Analyst, Code Reviewer, and Summary Generator.

Each agent is a specialized prompt sent to Amazon Bedrock.
The Supervisor orchestrates them in sequence and records results.
"""

from __future__ import annotations

import logging
import time

from bedrock_client import invoke_model
from github_client import update_pr_body, post_pr_comment
from store import AgentResult, PRRecord, pr_store
from teams_notifier import send_teams_notification
from activity_log import activity_log

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent 1 – Diff Analysis Agent
# ---------------------------------------------------------------------------

def diff_analysis_agent(diff: str, files: list[dict]) -> tuple[str, int]:
    """Analyze the diff and categorize changes. Returns (output, duration_ms)."""
    file_summary = "\n".join(
        f"- {f['filename']} (+{f['additions']} -{f['deletions']} | {f['status']})"
        for f in files
    )
    prompt = f"""You are a Diff Analysis Agent. Your job is to analyze a pull request diff
and produce a structured breakdown.

## Changed Files
{file_summary}

## Raw Diff (truncated to 12 000 chars)
{diff[:12000]}

Produce the following:
1. **Change Category**: Is this a feature, bugfix, refactor, docs update, config change, or mixed?
2. **Files Changed Summary**: Group files by area (e.g., backend, frontend, tests, config).
3. **Key Modifications**: List the most important code changes (max 10 bullet points).
4. **Risk Assessment**: Low / Medium / High — with a one-line justification.

Be concise and factual."""

    start = time.time()
    result = invoke_model(prompt)
    duration = int((time.time() - start) * 1000)
    return result, duration


# ---------------------------------------------------------------------------
# Agent 2 – Code Review Agent
# ---------------------------------------------------------------------------

def code_review_agent(diff: str) -> tuple[str, int]:
    """Review code quality, security, and best practices. Returns (output, duration_ms)."""
    prompt = f"""You are a Code Review Agent. Analyze the following pull request diff for:

1. **Code Quality Issues**: naming, complexity, duplication
2. **Security Concerns**: hardcoded secrets, injection risks, auth gaps
3. **Best Practice Violations**: error handling, logging, typing
4. **Positive Highlights**: well-written code worth calling out

## Diff (truncated to 12 000 chars)
{diff[:12000]}

Keep feedback actionable. Use bullet points. Max 15 items total."""

    start = time.time()
    result = invoke_model(prompt)
    duration = int((time.time() - start) * 1000)
    return result, duration


# ---------------------------------------------------------------------------
# Agent 3 – Summary Generator Agent
# ---------------------------------------------------------------------------

def summary_generator_agent(
    pr_details: dict,
    diff_analysis: str,
    code_review: str,
) -> tuple[str, int]:
    """Generate a human-readable MR summary. Returns (output, duration_ms)."""
    prompt = f"""You are a Summary Generator Agent. Combine the inputs below into a
polished pull request summary that a developer can read in under 2 minutes.

## PR Metadata
- **Title**: {pr_details.get("title", "N/A")}
- **Author**: {pr_details.get("user", {}).get("login", "N/A")}
- **Branch**: {pr_details.get("head", {}).get("ref", "N/A")} → {pr_details.get("base", {}).get("ref", "N/A")}
- **Description**: {(pr_details.get("body") or "No description provided.")[:2000]}

## Diff Analysis (from Diff Agent)
{diff_analysis}

## Code Review (from Review Agent)
{code_review}

Produce a Markdown comment with these sections:
1. 🔍 **Overview** — 2-3 sentence summary of what this PR does.
2. 📂 **Changes Breakdown** — grouped by area.
3. ⚠️ **Review Highlights** — top issues or praise from the code review.
4. 📊 **Risk Level** — Low / Medium / High with reasoning.
5. ✅ **Recommendation** — Approve, Request Changes, or Needs Discussion.

Start the comment with: `## 🤖 AI-Generated PR Summary`"""

    start = time.time()
    result = invoke_model(prompt)
    duration = int((time.time() - start) * 1000)
    return result, duration


def _extract_risk_level(summary: str) -> str:
    """Extract risk level from the generated summary."""
    text = summary.lower()
    if "risk level" in text:
        after = text.split("risk level")[-1][:100]
        if "high" in after:
            return "High"
        if "medium" in after:
            return "Medium"
        if "low" in after:
            return "Low"
    return "Unknown"


def _extract_pr_type(diff_analysis: str) -> str:
    """Extract PR type (feature, bugfix, refactor, etc.) from diff analysis output."""
    text = diff_analysis.lower()

    # Look for the change category section
    for marker in ["change category", "category"]:
        if marker in text:
            after = text.split(marker)[-1][:200]
            if "bugfix" in after or "bug fix" in after or "bug" in after:
                return "🐛 Bugfix"
            if "feature" in after or "new feature" in after:
                return "✨ Feature"
            if "refactor" in after:
                return "♻️ Refactor"
            if "docs" in after or "documentation" in after:
                return "📝 Docs"
            if "config" in after or "configuration" in after:
                return "⚙️ Config"
            if "test" in after:
                return "🧪 Test"
            if "mixed" in after:
                return "🔀 Mixed"
            break

    # Fallback: scan the whole text
    if "bugfix" in text or "bug fix" in text or "fixes bug" in text:
        return "🐛 Bugfix"
    if "feature" in text or "new functionality" in text:
        return "✨ Feature"
    if "refactor" in text:
        return "♻️ Refactor"

    return "❓ Unknown"


# ---------------------------------------------------------------------------
# Agent 4 – Priority Assessment Agent
# ---------------------------------------------------------------------------

def priority_agent(
    pr_details: dict,
    diff_analysis: str,
    files: list[dict],
) -> tuple[str, int]:
    """Assess PR priority based on code changes and context. Returns (output, duration_ms)."""
    file_list = ", ".join(f["filename"] for f in files[:20])
    total_changes = sum(f.get("additions", 0) + f.get("deletions", 0) for f in files)

    prompt = f"""You are a Priority Assessment Agent. Determine the priority of this pull request.

## PR Info
- Title: {pr_details.get("title", "N/A")}
- Description: {(pr_details.get("body") or "None")[:1000]}
- Branch: {pr_details.get("head", {}).get("ref", "N/A")}
- Files changed: {len(files)} ({total_changes} total line changes)
- Files: {file_list}

## Diff Analysis
{diff_analysis[:3000]}

Assess priority as one of: Critical, High, Medium, Low

Use these criteria:
- **Critical**: Security fixes, production hotfixes, data loss prevention, breaking changes that block others
- **High**: Bug fixes affecting users, important features with deadlines, changes to auth/payment/core logic
- **Medium**: Standard features, non-urgent improvements, moderate refactors
- **Low**: Documentation, minor style changes, test-only changes, config tweaks

Respond in EXACTLY this format (first line must be the priority):
PRIORITY: <Critical|High|Medium|Low>
REASON: <one sentence explanation>"""

    start = time.time()
    result = invoke_model(prompt, max_tokens=200)
    duration = int((time.time() - start) * 1000)
    return result, duration


def _extract_priority(priority_output: str) -> str:
    """Extract priority level from priority agent output."""
    text = priority_output.lower()
    for line in text.split("\n"):
        if "priority" in line:
            if "critical" in line:
                return "🔥 Critical"
            if "high" in line:
                return "🔴 High"
            if "medium" in line:
                return "🟡 Medium"
            if "low" in line:
                return "🟢 Low"
    return "🟡 Medium"


# ---------------------------------------------------------------------------
# Supervisor – Orchestrates the agents
# ---------------------------------------------------------------------------

def supervisor(pr_details: dict, diff: str, files: list[dict], repo: str, pr_number: int) -> str:
    """Run all agents in sequence, store results, and return the final summary."""
    agent_results = []
    pr_title = pr_details.get("title", "N/A")

    activity_log.emit("Supervisor", "started", f"Processing PR #{pr_number}: {pr_title}", repo=repo, pr_number=pr_number)

    # Step 1: Diff Analysis
    activity_log.emit("Diff Analysis", "started", "Analyzing diff and categorizing changes...", repo=repo, pr_number=pr_number)
    diff_output, diff_dur = diff_analysis_agent(diff, files)
    activity_log.emit("Diff Analysis", "completed", f"Categorized {len(files)} files", repo=repo, pr_number=pr_number, duration_ms=diff_dur)
    agent_results.append(AgentResult(name="Diff Analysis", output=diff_output, duration_ms=diff_dur))

    # Step 2: Code Review
    activity_log.emit("Code Review", "started", "Reviewing code quality and security...", repo=repo, pr_number=pr_number)
    review_output, review_dur = code_review_agent(diff)
    activity_log.emit("Code Review", "completed", "Code review complete", repo=repo, pr_number=pr_number, duration_ms=review_dur)
    agent_results.append(AgentResult(name="Code Review", output=review_output, duration_ms=review_dur))

    # Step 3: Generate Summary
    activity_log.emit("Summary Generator", "started", "Generating PR summary...", repo=repo, pr_number=pr_number)
    summary_output, summary_dur = summary_generator_agent(pr_details, diff_output, review_output)
    activity_log.emit("Summary Generator", "completed", "Summary generated", repo=repo, pr_number=pr_number, duration_ms=summary_dur)
    agent_results.append(AgentResult(name="Summary Generator", output=summary_output, duration_ms=summary_dur))

    # Step 4: Priority Assessment
    activity_log.emit("Priority Assessment", "started", "Assessing PR priority...", repo=repo, pr_number=pr_number)
    priority_output, priority_dur = priority_agent(pr_details, diff_output, files)
    activity_log.emit("Priority Assessment", "completed", "Priority assessed", repo=repo, pr_number=pr_number, duration_ms=priority_dur)
    agent_results.append(AgentResult(name="Priority Assessment", output=priority_output, duration_ms=priority_dur))

    total_dur = diff_dur + review_dur + summary_dur + priority_dur
    risk = _extract_risk_level(summary_output)
    pr_type = _extract_pr_type(diff_output)
    priority = _extract_priority(priority_output)

    total_additions = sum(f.get("additions", 0) for f in files)
    total_deletions = sum(f.get("deletions", 0) for f in files)

    record = PRRecord(
        repo=repo,
        pr_number=pr_number,
        title=pr_details.get("title", "N/A"),
        author=pr_details.get("user", {}).get("login", "N/A"),
        branch=pr_details.get("head", {}).get("ref", "N/A"),
        target=pr_details.get("base", {}).get("ref", "N/A"),
        action="summary",
        summary=summary_output,
        risk_level=risk,
        pr_type=pr_type,
        priority=priority,
        agent_results=agent_results,
        total_duration_ms=total_dur,
        files_changed=len(files),
        additions=total_additions,
        deletions=total_deletions,
    )
    pr_store.add(record)

    activity_log.emit("Supervisor", "completed", f"All agents finished — {pr_type} | {priority} | Risk: {risk}", repo=repo, pr_number=pr_number, duration_ms=total_dur)

    # Broadcast PR notification via WebSocket
    try:
        import asyncio
        from app.services.websocket_manager import get_websocket_manager
        manager = get_websocket_manager()
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(manager.broadcast_notification({
                "notification_type": "pr_analyzed",
                "repo": repo,
                "pr_number": pr_number,
                "title": record.title,
                "author": record.author,
                "risk_level": risk,
                "pr_type": pr_type,
                "priority": priority,
                "files_changed": len(files),
                "timestamp": time.time(),
            }))
    except Exception:
        pass  # Silently fail if WebSocket not available

    # Send Teams notification
    send_teams_notification(
        repo=repo,
        pr_number=pr_number,
        title=record.title,
        author=record.author,
        branch=record.branch,
        target=record.target,
        risk_level=risk,
        pr_type=pr_type,
        priority=priority,
        summary=summary_output,
        files_changed=len(files),
        additions=total_additions,
        deletions=total_deletions,
        duration_ms=total_dur,
    )

    return summary_output

# ---------------------------------------------------------------------------
# Agent 5 – PR Description Generator Agent
# ---------------------------------------------------------------------------

def description_generator_agent(pr_details: dict, diff: str, files: list[dict]) -> tuple[str, int]:
    """Generate a PR description from the diff when the author left it empty.
    Returns (description_markdown, duration_ms)."""
    file_summary = "\n".join(
        f"- {f['filename']} (+{f['additions']} -{f['deletions']} | {f['status']})"
        for f in files
    )
    prompt = f"""You are a PR Description Generator Agent. A developer opened a pull request
but left the description empty. Generate a clear, professional PR description from the diff.

## PR Metadata
- Title: {pr_details.get("title", "N/A")}
- Author: {pr_details.get("user", {}).get("login", "N/A")}
- Branch: {pr_details.get("head", {}).get("ref", "N/A")} → {pr_details.get("base", {}).get("ref", "N/A")}

## Changed Files
{file_summary}

## Raw Diff (truncated to 12 000 chars)
{diff[:12000]}

Generate a Markdown PR description with these sections:
## Summary
A 2-3 sentence overview of what this PR does and why.

## Changes
- Bullet list of key changes grouped by area.

## Testing
- Suggested testing steps or areas to verify.

Keep it concise, factual, and developer-friendly. Do NOT include a title line — just the body content.
End with a small note: `---\n_📝 This description was auto-generated by SynapseOps AI Agent._`"""

    start = time.time()
    result = invoke_model(prompt)
    duration = int((time.time() - start) * 1000)
    return result, duration


def check_and_generate_description(pr_details: dict, diff: str, files: list[dict],
                                    repo: str, pr_number: int) -> bool:
    """Check if PR has an empty description and auto-generate one.
    Returns True if a description was generated and updated."""
    body = (pr_details.get("body") or "").strip()

    if body:
        return False

    logger.info("PR #%s on %s has empty description — generating one...", pr_number, repo)
    activity_log.emit("Description Generator", "started", "PR has empty description — generating...", repo=repo, pr_number=pr_number)

    desc, duration = description_generator_agent(pr_details, diff, files)
    update_pr_body(repo, pr_number, desc)
    post_pr_comment(repo, pr_number,
        "📝 **Auto-Generated Description**: This PR had an empty description, "
        "so SynapseOps AI Agent generated one from the diff. "
        f"_(took {duration / 1000:.1f}s)_"
    )

    activity_log.emit("Description Generator", "completed", "Description generated and updated on PR", repo=repo, pr_number=pr_number, duration_ms=duration)
    logger.info("✅ Auto-generated description for PR #%s (%dms)", pr_number, duration)
    return True

