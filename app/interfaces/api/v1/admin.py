from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.infrastructure.sync.manager import sync_entity
from app.infrastructure.external.client import MockExternalClient

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# We need a client instance for the sync function
# In a real app, this might be a dependency injection or singleton
external_client = MockExternalClient()

@router.post("/sync/{entity_type}", tags=["Admin"])
async def force_sync(
    entity_type: str, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Trigger an immediate sync for a specific entity type.
    Runs in background to return response immediately.
    """
    if entity_type not in ["incident", "change", "event"]:
        raise HTTPException(status_code=400, detail="Invalid entity type")

    # Wrapper to manage DB session in background task
    def run_sync_task():
        # Create new session for background task
        bg_db = SessionLocal()
        try:
            sync_entity(bg_db, entity_type, external_client)
        finally:
            bg_db.close()

    background_tasks.add_task(run_sync_task)
    
    return {"message": f"Sync triggered for {entity_type}", "status": "processing"}
