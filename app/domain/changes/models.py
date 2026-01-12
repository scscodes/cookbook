from sqlalchemy import Column, String, Text, DateTime, Boolean, func, Integer
from app.core.database import Base
from app.core.models_mixins import TimestampMixin

class Change(Base, TimestampMixin):
    __tablename__ = "changes"

    external_id = Column(String(100), primary_key=True)
    external_modified_at = Column(DateTime, nullable=False, index=True)
    local_synced_at = Column(DateTime, nullable=False, server_default=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)

    number = Column(String(50), nullable=False, index=True)
    short_description = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    state = Column(String(50), nullable=False, index=True)
    risk = Column(String(50), nullable=True)
    change_type = Column(String(50), nullable=True)
    requested_by = Column(String(100), nullable=True)
    assigned_to = Column(String(100), nullable=True, index=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Change(number={self.number}, state={self.state})>"
