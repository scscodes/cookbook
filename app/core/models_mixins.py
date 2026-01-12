from sqlalchemy import Column, DateTime, func
from app.core.database import Base

class TimestampMixin:
    """Mixin for standard timestamp tracking."""
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
