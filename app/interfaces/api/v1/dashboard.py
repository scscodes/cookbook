from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.core.database import SessionLocal
from app.domain.incidents.models import Incident
from app.domain.changes.models import Change
from app.domain.events.models import Event
from datetime import datetime
from typing import List, Dict

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/overview", tags=["Dashboard"])
def get_dashboard_overview(db: Session = Depends(get_db)):
    """
    Aggregated 'Single Pane of Glass' view.
    Fetches high-priority items from all domains in a single low-latency call.
    """
    # 1. Critical Incidents (P1/P2)
    critical_incidents = db.query(Incident)\
        .filter(Incident.priority <= 2, Incident.state != 'closed')\
        .order_by(desc(Incident.opened_at))\
        .limit(5).all()

    # 2. Upcoming High-Risk Changes
    upcoming_changes = db.query(Change)\
        .filter(Change.state != 'closed')\
        .filter(Change.change_type == 'emergency')\
        .order_by(desc(Change.start_date))\
        .limit(5).all()

    # 3. Active Critical Alerts
    active_events = db.query(Event)\
        .filter(Event.severity == 1, Event.state == 'open')\
        .order_by(desc(Event.opened_at))\
        .limit(10).all()

    return {
        "summary": {
            "incidents_critical": len(critical_incidents),
            "changes_emergency": len(upcoming_changes),
            "events_critical": len(active_events)
        },
        "critical_incidents": [
            {
                "number": i.number, 
                "priority": i.priority, 
                "title": i.short_description, 
                "age_hours": int((datetime.utcnow() - i.opened_at).total_seconds()/3600)
            } for i in critical_incidents
        ],
        "emergency_changes": [
            {
                "number": c.number,
                "risk": c.risk,
                "start": c.start_date
            } for c in upcoming_changes
        ],
        "active_alerts": [
            {
                "source": e.source,
                "node": e.node,
                "message": e.message_key
            } for e in active_events
        ]
    }
