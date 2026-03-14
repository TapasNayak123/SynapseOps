from contextlib import asynccontextmanager
from fastapi import FastAPI
import structlog

from app.config import get_settings
from app.routes import metrics, chat, alerts
from app.tasks.scheduler import start_scheduler, stop_scheduler

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()


def _seed_monitored_apis():
    """Load monitored APIs from config into Redis on startup."""
    settings = get_settings()
    if settings.monitored_apis:
        from app.services.cache import CacheService
        cache = CacheService()
        existing = cache.get("monitored_apis")
        if not existing:
            api_list = [a.strip() for a in settings.monitored_apis.split(",") if a.strip()]
            cache.set("monitored_apis", api_list, ttl_seconds=86400 * 30)
            logger.info("seeded_monitored_apis", count=len(api_list))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting_synapse_ops_agent")
    _seed_monitored_apis()
    start_scheduler()
    yield
    stop_scheduler()
    logger.info("synapse_ops_agent_stopped")


app = FastAPI(
    title="SynapseOps - Intelligent API Monitoring Agent",
    description=(
        "AI-powered observability agent that monitors CloudWatch metrics, "
        "analyzes errors, detects anomalies, predicts threshold breaches, "
        "tracks SLA compliance, correlates deployments, and provides "
        "auto-remediation suggestions via Amazon Bedrock."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(metrics.router)
app.include_router(chat.router)
app.include_router(alerts.router)


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "synapse-ops"}
