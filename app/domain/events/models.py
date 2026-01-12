from sqlalchemy import Column, String, Integer, Text, DateTime, Boolean, func
from app.core.database import Base
from app.core.models_mixins import TimestampMixin

class Event(Base, TimestampMixin):
    __tablename__ = "events"

    external_id = Column(String(100), primary_key=True)
    external_modified_at = Column(DateTime, nullable=False, index=True)
    local_synced_at = Column(DateTime, nullable=False, server_default=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)

    number = Column(String(50), nullable=False, index=True)
    source = Column(String(100), nullable=False)
    severity = Column(Integer, nullable=False, index=True)
    node = Column(String(100), nullable=True, index=True)
    message_key = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    state = Column(String(50), nullable=False, index=True)
    opened_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Event(number={self.number}, severity={self.severity})>"
