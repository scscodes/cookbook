from sqlalchemy.orm import Session
from app.domain.incidents.models import Incident

class IncidentService:
    """
    Domain Service for Incident logic.
    This logic is independent of how the data was acquired (sync).
    """
    def __init__(self, db: Session):
        self.db = db

    def analyze_risk(self, incident_id: str) -> dict:
        incident = self.db.query(Incident).filter(Incident.external_id == incident_id).first()
        if not incident:
            return {"error": "Incident not found"}
            
        risk_score = 0
        factors = []
        
        # Priority Logic
        if incident.priority == 1:
            risk_score += 50
            factors.append("Critical Priority")
        elif incident.priority == 2:
            risk_score += 30
            factors.append("High Priority")
            
        # State Logic
        if incident.state == "new":
            risk_score += 10
            factors.append("New/Untriaged")
            
        return {
            "incident_number": incident.number,
            "risk_score": risk_score,
            "risk_factors": factors,
            "recommendation": "Escalate" if risk_score > 40 else "Monitor"
        }
