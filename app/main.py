"""SynapseOps - Intelligent API Monitoring Agent."""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import structlog

from app.config import get_settings
from app.routes import metrics, chat, alerts
from app.tasks.scheduler import start_scheduler, stop_scheduler

structlog.configure(processors=[
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.add_log_level,
    structlog.processors.JSONRenderer(),
])
logger = structlog.get_logger()


def _seed_monitored_apis():
    settings = get_settings()
    if settings.monitored_apis:
        from app.services.cache import CacheService
        cache = CacheService()
        if not cache.get("monitored_apis"):
            apis = [a.strip() for a in settings.monitored_apis.split(",") if a.strip()]
            cache.set("monitored_apis", apis, ttl_seconds=86400 * 30)
            logger.info("seeded_apis", count=len(apis))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting")
    _seed_monitored_apis()
    start_scheduler()
    yield
    stop_scheduler()
    logger.info("stopped")


app = FastAPI(title="SynapseOps", version="1.0.0", lifespan=lifespan)
app.include_router(metrics.router)
app.include_router(chat.router)
app.include_router(alerts.router)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/chat")
def chat_ui():
    return FileResponse(str(STATIC_DIR / "chat.html"))


@app.get("/health")
def health():
    return {"status": "healthy", "service": "synapse-ops"}


@app.get("/health/ready")
def readiness():
    from app.services.cache import CacheService
    from app.services.dynamodb import DynamoDBService
    r = CacheService().ping()
    d = DynamoDBService().ping()
    return {"status": "ready" if r and d else "degraded",
            "redis": "ok" if r else "error", "dynamodb": "ok" if d else "error"}
