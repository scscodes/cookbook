from contextlib import asynccontextmanager
from fastapi import FastAPI
import logging

from app.core.config import settings
from app.core.database import init_db, SessionLocal
from app.infrastructure.sync.scheduler import SyncScheduler
from app.infrastructure.external.client import MockExternalClient
from app.interfaces.api.v1 import incidents, changes, events, health, admin, dashboard

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize Global Components
external_client = MockExternalClient()
sync_scheduler = SyncScheduler(
    db_session_factory=SessionLocal,
    external_api_client=external_client,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan event handler.
    Handles startup and shutdown logic.
    """
    # 1. Initialize Database (Create tables if not exist)
    logger.info("Initializing database...")
    init_db()
    
    # 2. Start Scheduler
    logger.info("Starting sync scheduler...")
    sync_scheduler.start()
    
    yield
    
    # 3. Shutdown Scheduler
    logger.info("Shutting down sync scheduler...")
    sync_scheduler.shutdown()

app = FastAPI(
    title="Cookbook Cache Sync POC",
    description="POC for watermark-based incremental sync with SQLite/Postgres",
    version="0.1.0",
    lifespan=lifespan
)

# Register Domain Routers
app.include_router(incidents.router, prefix="/api/v1/incidents", tags=["Incidents"])
app.include_router(changes.router, prefix="/api/v1/changes", tags=["Changes"])
app.include_router(events.router, prefix="/api/v1/events", tags=["Events"])
app.include_router(health.router, prefix="/api/v1/health", tags=["Health"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])

@app.get("/")
def root():
    return {
        "message": "Welcome to the Cookbook Cache Sync POC",
        "docs": "/docs",
        "health": "/api/v1/health/sync"
    }
