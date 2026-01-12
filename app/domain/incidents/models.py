from sqlalchemy import Column, String, Integer, Text, DateTime, Boolean, func
from app.core.database import Base
from app.core.models_mixins import TimestampMixin

class Incident(Base, TimestampMixin):
    """
    Incident Domain Entity.
    """
    __tablename__ = "incidents"

    # Identity
    external_id = Column(String(100), primary_key=True, comment="Source system ID")
    
    # Sync Metadata (Infrastructure concern mixed in for simplicity in Active Record, 
    # but strictly speaking belongs to the persistence layer. Kept here for practical reasons.)
    external_modified_at = Column(DateTime, nullable=False, index=True)
    local_synced_at = Column(DateTime, nullable=False, server_default=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)

    # Business Fields
    number = Column(String(50), nullable=False, index=True)
    short_description = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    state = Column(String(50), nullable=False, index=True)
    priority = Column(Integer, nullable=False, index=True)
    urgency = Column(Integer, nullable=True)
    impact = Column(Integer, nullable=True)
    assigned_to = Column(String(100), nullable=True, index=True)
    assignment_group = Column(String(100), nullable=True, index=True)
    opened_at = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Incident(number={self.number}, state={self.state})>"
