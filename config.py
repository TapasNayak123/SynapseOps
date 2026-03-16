import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-pro-v1:0")

# Comma-separated list of repos to watch, e.g. "owner/repo1,owner/repo2"
WATCH_REPOS = [r.strip() for r in os.getenv("WATCH_REPOS", "").split(",") if r.strip()]
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))

# Microsoft Teams incoming webhook URL
TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL", "")

# Base URL of this app (for Teams action buttons)
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:5000")
