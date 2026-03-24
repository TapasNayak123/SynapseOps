"""GitHub Actions deployment tracking and error correlation."""
import structlog
from datetime import datetime, timedelta
from app.config import get_settings
from app.services.dynamodb import DynamoDBService
from github_client import gh_headers, GITHUB_API, _get_session

logger = structlog.get_logger()


class DeploymentTracker:
    def __init__(self):
        self.settings = get_settings()
        self.db = DynamoDBService()

    def get_recent_deployments(self, hours_back: int = 24) -> list[dict]:
        if not self.settings.github_token or not self.settings.github_repo:
            return []

        try:
            resp = _get_session().get(
                f"{GITHUB_API}/repos/{self.settings.github_repo}/actions/runs",
                headers=gh_headers(),
                params={"status": "completed", "per_page": 20},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            cutoff = datetime.utcnow() - timedelta(hours=hours_back)
            deployments = []
            monitor_branch = self.settings.monitor_branch
            for run in data.get("workflow_runs", []):
                created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00")).replace(tzinfo=None)
                if created < cutoff:
                    continue
                if monitor_branch and run.get("head_branch", "") != monitor_branch:
                    continue
                deployments.append({
                    "id": run["id"], "name": run["name"], "status": run["conclusion"],
                    "branch": run["head_branch"], "commit_sha": run["head_sha"][:8],
                    "commit_message": run.get("head_commit", {}).get("message", ""),
                    "started_at": run["created_at"], "completed_at": run.get("updated_at", ""),
                    "url": run["html_url"],
                })
            return deployments
        except Exception as e:
            logger.error("github_fetch_failed", error=str(e))
            return []

    def correlate_with_errors(self, api_path: str, hours_back: int = 6) -> dict:
        deployments = self.get_recent_deployments(hours_back)
        alerts = self.db.get_alerts(api_path, limit=20)

        correlations = []
        for alert in alerts:
            try:
                alert_ts = alert.get("sk", alert.get("timestamp", ""))
                if not alert_ts:
                    continue
                alert_time = datetime.fromisoformat(str(alert_ts).replace("Z", "+00:00")).replace(tzinfo=None)
            except (ValueError, TypeError):
                continue
            for deploy in deployments:
                deploy_time = datetime.fromisoformat(deploy["completed_at"].replace("Z", "+00:00")).replace(tzinfo=None)
                diff = abs((alert_time - deploy_time).total_seconds())
                if diff <= 1800:  # 30 min
                    correlations.append({
                        "alert_timestamp": alert_time.isoformat(), "alert_type": alert.get("alert_type", ""),
                        "deployment": deploy, "time_diff_seconds": int(diff), "likely_cause": diff <= 600,
                    })

        return {"api_path": api_path, "recent_deployments": len(deployments),
                "correlations_found": len(correlations), "correlations": correlations}
