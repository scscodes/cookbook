from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.domain.changes.models import Change

from app.domain.changes.service import ChangeService

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", tags=["Changes"])
def list_changes(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Change).offset(skip).limit(limit).all()

@router.get("/{change_id}/risk", tags=["Changes"])
def assess_change_risk(change_id: str, db: Session = Depends(get_db)):
    """
    Evaluate change risk based on type, timing, and declared risk.
    """
    service = ChangeService(db)
    return service.assess_risk(change_id)
