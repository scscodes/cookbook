from sqlalchemy.orm import Session
from app.domain.changes.models import Change
from datetime import datetime

class ChangeService:
    """
    Domain Service for Change Management logic.
    """
    def __init__(self, db: Session):
        self.db = db

    def assess_risk(self, change_id: str) -> dict:
        change = self.db.query(Change).filter(Change.external_id == change_id).first()
        if not change:
            return {"error": "Change not found"}
            
        risk_score = 0
        warnings = []
        
        # 1. Type Risk
        if change.change_type == "emergency":
            risk_score += 40
            warnings.append("Emergency Change Type")
        elif change.change_type == "normal":
            risk_score += 10
            
        # 2. Declared Risk
        if change.risk == "high":
            risk_score += 30
            warnings.append("High Declared Risk")
            
        # 3. Lead Time / Schedule Risk
        # If start date is very close to open date (simulating lack of lead time)
        if change.start_date and change.opened_at:
            lead_time_hours = (change.start_date - change.opened_at).total_seconds() / 3600
            if lead_time_hours < 24 and change.change_type != "standard":
                risk_score += 20
                warnings.append("Short Lead Time (<24h)")

        # 4. Weekend Work (Simple heuristic: is start_date a Sat/Sun?)
        if change.start_date and change.start_date.weekday() >= 5:
            risk_score += 15
            warnings.append("Scheduled on Weekend")

        return {
            "change_number": change.number,
            "calculated_risk_score": min(risk_score, 100),
            "approval_status": "Required Board Review" if risk_score > 50 else "Standard Approval",
            "risk_factors": warnings,
            "schedule": {
                "start": change.start_date,
                "end": change.end_date
            }
        }
