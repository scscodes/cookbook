from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.infrastructure.sync.manager import get_sync_health

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/sync", tags=["Health"])
def sync_status(db: Session = Depends(get_db)):
    return get_sync_health(db)
