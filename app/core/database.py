from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine
from app.core.config import settings, DatabaseType
# Import Base to be shared
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

def get_engine() -> Engine:
    """Create database engine based on configuration."""
    if settings.DB_TYPE == DatabaseType.SQLITE:
        # SQLite specific configuration
        engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False},  # Needed for FastAPI/Threads
            echo=False
        )
        
        # Enable Write-Ahead Logging (WAL) for concurrency
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()
            
    else:
        # PostgreSQL configuration
        engine = create_engine(
            settings.database_url,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True
        )

    return engine

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Idempotent initialization of database tables."""
    # Import all models to ensure they are registered with Base.metadata
    from app.domain.incidents.models import Incident
    from app.domain.changes.models import Change
    from app.domain.events.models import Event
    from app.infrastructure.persistence.models import SyncWatermark
    
    # Create tables
    Base.metadata.create_all(bind=engine)
