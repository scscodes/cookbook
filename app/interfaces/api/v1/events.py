from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.domain.events.models import Event
from app.domain.events.service import EventService

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", tags=["Events"])
def list_events(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List events from the local cache."""
    return db.query(Event).offset(skip).limit(limit).all()

@router.get("/{event_id}/impact", tags=["Events"])
def analyze_event_impact(event_id: str, db: Session = Depends(get_db)):
    """
    Demonstrates domain logic for events.
    Calculates impact score based on severity, node type, and freshness.
    """
    service = EventService(db)
    return service.analyze_impact(event_id)
