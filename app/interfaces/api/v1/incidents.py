from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.domain.incidents.models import Incident
from app.domain.incidents.service import IncidentService

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", tags=["Incidents"])
def list_incidents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Incident).offset(skip).limit(limit).all()

@router.get("/{incident_id}/risk", tags=["Incidents"])
def analyze_risk(incident_id: str, db: Session = Depends(get_db)):
    """Demonstrates domain logic separate from data sync."""
    service = IncidentService(db)
    return service.analyze_risk(incident_id)
