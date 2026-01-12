from typing import List, Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.core.config import settings, DatabaseType

def bulk_upsert(
    db: Session,
    model: Any,
    records: List[Dict[str, Any]],
    index_elements: List[str],
    update_columns: List[str]
) -> int:
    """
    Dialect-agnostic upsert operation.
    
    Args:
        db: Database session
        model: SQLAlchemy model class
        records: List of dictionaries to insert/update
        index_elements: List of column names that form the unique constraint (PK)
        update_columns: List of column names to update on conflict
    """
    if not records:
        return 0

    if settings.DB_TYPE == DatabaseType.POSTGRES:
        stmt = pg_insert(model).values(records)
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=index_elements,
            set_={col: stmt.excluded[col] for col in update_columns}
        )
    else:
        # SQLite implementation
        stmt = sqlite_insert(model).values(records)
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=index_elements,
            set_={col: stmt.excluded[col] for col in update_columns}
        )

    result = db.execute(upsert_stmt)
    db.commit()
    
    # SQLite .rowcount behavior varies, returning len(records) is a safe approximation 
    # for "processed" records in this context.
    return len(records)
