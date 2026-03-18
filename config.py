"""Root config — re-exports settings from app.config (single source of truth).

Modules that do `from config import GITHUB_TOKEN` continue to work unchanged.
"""

from app.config import get_settings as _get_settings

_s = _get_settings()

GITHUB_TOKEN = _s.github_token
GITHUB_WEBHOOK_SECRET = _s.github_webhook_secret
AWS_REGION = _s.aws_region
BEDROCK_MODEL_ID = _s.bedrock_model_id
TEAMS_WEBHOOK_URL = _s.teams_webhook_url
APP_BASE_URL = _s.app_base_url
GITHUB_REPO = _s.github_repo
