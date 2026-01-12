from sqlalchemy import Column, String, DateTime, Enum, Text, Integer
from app.core.database import Base
from app.core.models_mixins import TimestampMixin
from datetime import datetime
from typing import Optional

class SyncWatermark(Base, TimestampMixin):
    __tablename__ = "sync_watermarks"

    entity_type = Column(String(50), primary_key=True)
    last_success_at = Column(DateTime, nullable=True)
    last_attempt_at = Column(DateTime, nullable=True)
    status = Column(
        Enum("success", "failed", "in_progress", name="sync_status_enum"),
        nullable=False,
        default="success"
    )
    error_message = Column(Text, nullable=True)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    records_synced = Column(Integer, nullable=True)
    sync_duration_seconds = Column(Integer, nullable=True)

    @property
    def staleness_seconds(self) -> Optional[int]:
        if not self.last_success_at:
            return None
        return int((datetime.utcnow() - self.last_success_at).total_seconds())

    @property
    def is_healthy(self) -> bool:
        if self.consecutive_failures >= 3:
            return False
        if not self.last_success_at:
            return False
        if self.staleness_seconds and self.staleness_seconds > 3600:
            return False
        return True
