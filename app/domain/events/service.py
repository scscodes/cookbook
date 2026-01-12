from sqlalchemy.orm import Session
from app.domain.events.models import Event
from datetime import datetime, timedelta

class EventService:
    """
    Domain Service for Event logic.
    Provides business logic for analyzing event patterns.
    """
    def __init__(self, db: Session):
        self.db = db

    def analyze_impact(self, event_id: str) -> dict:
        event = self.db.query(Event).filter(Event.external_id == event_id).first()
        if not event:
            return {"error": "Event not found"}
            
        impact_score = 0
        analysis = []
        
        # Severity Logic
        # Assuming severity 1 is critical, 5 is info
        if event.severity == 1:
            impact_score += 90
            analysis.append("Critical Severity")
        elif event.severity == 2:
            impact_score += 60
            analysis.append("Major Severity")
        elif event.severity <= 3:
            impact_score += 30
            analysis.append("Minor/Warning Severity")
            
        # Node Context Logic
        if "db" in (event.node or "").lower():
            impact_score += 20
            analysis.append("Database Node Affected")
        
        # Freshness Logic
        age = (datetime.utcnow() - event.opened_at).total_seconds() / 60
        if age < 15 and event.state != "closed":
            impact_score += 10
            analysis.append("Fresh Alert (<15m)")

        return {
            "event_number": event.number,
            "impact_score": min(impact_score, 100),
            "analysis": analysis,
            "automated_action": "Page On-Call" if impact_score > 80 else "Log Ticket"
        }
