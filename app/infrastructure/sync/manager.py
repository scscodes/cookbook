"""
Sync workflow implementation for periodic cache refresh.

This module handles:
- Watermark-based incremental sync from external APIs
- Lock management to prevent concurrent runs
- Error handling and retry logic
- Metrics and observability
"""

import logging
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Generator, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.changes.models import Change
from app.domain.events.models import Event
from app.domain.incidents.models import Incident
from app.infrastructure.persistence.models import SyncWatermark
from app.core.config import settings, DatabaseType
from app.infrastructure.persistence.ops import bulk_upsert

logger = logging.getLogger(__name__)

# Map entity types to cache models
CACHE_MODELS = {
    "incident": Incident,
    "change": Change,
    "event": Event,
}


class SyncLockError(Exception):
    """Raised when sync lock cannot be acquired."""

    pass


@contextmanager
def sync_lock(
    db: Session, entity_type: str, timeout_seconds: int = 300
) -> Generator[SyncWatermark, None, None]:
    """
    Context manager for sync job locking.

    Acquires an exclusive lock on the watermark row to prevent concurrent
    sync jobs. Updates status to 'in_progress' on entry and back to
    'success'/'failed' on exit.

    Args:
        db: Database session
        entity_type: Entity to sync (incident, change, event)
        timeout_seconds: How long to wait for stuck locks

    Raises:
        SyncLockError: If lock cannot be acquired

    Yields:
        SyncWatermark: The locked watermark record
    """
    # Fetch watermark
    # Note: SQLite doesn't support SELECT FOR UPDATE.
    # We rely on transaction isolation and application-level status check.
    stmt = select(SyncWatermark).where(SyncWatermark.entity_type == entity_type)
    
    if settings.DB_TYPE == DatabaseType.POSTGRES:
        stmt = stmt.with_for_update()
        
    watermark = db.execute(stmt).scalar_one_or_none()

    # Initialize watermark if doesn't exist
    if not watermark:
        watermark = SyncWatermark(entity_type=entity_type, status="success")
        db.add(watermark)
        db.commit()
        db.refresh(watermark)

    # Check if lock is stale (previous job crashed)
    if watermark.status == "in_progress":
        if watermark.last_attempt_at:
            age_seconds = (datetime.utcnow() - watermark.last_attempt_at).total_seconds()
            if age_seconds < timeout_seconds:
                raise SyncLockError(
                    f"Sync already in progress for {entity_type} "
                    f"(started {age_seconds:.0f}s ago)"
                )
            logger.warning(
                f"Clearing stale lock for {entity_type} "
                f"(stuck for {age_seconds:.0f}s)"
            )

    # Acquire lock
    watermark.status = "in_progress"
    watermark.last_attempt_at = datetime.utcnow()
    db.commit()

    try:
        yield watermark
    finally:
        # Release lock (caller should have set final status)
        db.commit()


def sync_entity(
    db: Session,
    entity_type: str,
    external_api_client: Any,
    batch_size: int = 100,
) -> int:
    """
    Perform incremental sync for a single entity type.

    Fetches records changed since last watermark, upserts into cache,
    and updates watermark on success.

    Args:
        db: Database session
        entity_type: Entity to sync (incident, change, event)
        external_api_client: Client for calling external ITSM API
        batch_size: Number of records to fetch per API call

    Returns:
        Number of records synced

    Raises:
        Exception: On API or database errors (caller should handle)
    """
    start_time = datetime.utcnow()
    total_synced = 0

    with sync_lock(db, entity_type) as watermark:
        try:
            # Determine starting watermark
            modified_since = watermark.last_success_at
            if not modified_since:
                # First sync - use cutoff date to avoid syncing entire history
                modified_since = datetime.utcnow() - timedelta(days=90)
                logger.info(
                    f"First sync for {entity_type}, using 90-day cutoff: {modified_since}"
                )

            logger.info(
                f"Starting sync for {entity_type} with watermark: {modified_since}"
            )

            # Fetch records from external API in batches
            # Note: This is a placeholder - adapt to your actual API client
            records = external_api_client.fetch_modified_since(
                entity_type=entity_type,
                modified_since=modified_since,
                batch_size=batch_size,
            )

            if records:
                total_synced = upsert_cache_records(
                    db=db,
                    entity_type=entity_type,
                    records=records,
                )
                logger.info(f"Synced {total_synced} {entity_type} records")

            # Update watermark on success
            watermark.last_success_at = datetime.utcnow()
            watermark.status = "success"
            watermark.error_message = None
            watermark.consecutive_failures = 0
            watermark.records_synced = total_synced
            watermark.sync_duration_seconds = int(
                (datetime.utcnow() - start_time).total_seconds()
            )

        except Exception as e:
            # Record failure
            watermark.status = "failed"
            watermark.error_message = str(e)
            watermark.consecutive_failures += 1
            logger.error(
                f"Sync failed for {entity_type} "
                f"(failure #{watermark.consecutive_failures}): {e}"
            )
            raise

    return total_synced


def upsert_cache_records(
    db: Session,
    entity_type: str,
    records: List[dict],
) -> int:
    """
    Bulk upsert records into cache table.

    Uses dialect-agnostic upsert via ops module.
    Updates existing records, inserts new ones.

    Args:
        db: Database session
        entity_type: Entity type (determines target table)
        records: List of record dicts from external API

    Returns:
        Number of records upserted
    """
    if not records:
        return 0

    model = CACHE_MODELS[entity_type]
    now = datetime.utcnow()

    # Transform external API records to cache table format
    cache_records = []
    for record in records:
        cache_record = {
            "external_id": record["sys_id"],  # Adjust field names per your API
            "external_modified_at": record["sys_updated_on"],
            "local_synced_at": now,
            "is_deleted": False,
            # Map business fields
            "number": record.get("number"),
            "short_description": record.get("short_description"),
            "description": record.get("description"),
            "state": record.get("state"),
            # Add other fields as needed
        }

        # Include entity-specific fields
        if entity_type == "incident":
            cache_record.update({
                "priority": record.get("priority"),
                "urgency": record.get("urgency"),
                "impact": record.get("impact"),
                "assigned_to": record.get("assigned_to"),
                "assignment_group": record.get("assignment_group"),
                "opened_at": record.get("opened_at"),
                "resolved_at": record.get("resolved_at"),
                "closed_at": record.get("closed_at"),
            })
        elif entity_type == "change":
            cache_record.update({
                "risk": record.get("risk"),
                "change_type": record.get("type"),
                "requested_by": record.get("requested_by"),
                "assigned_to": record.get("assigned_to"),
                "start_date": record.get("start_date"),
                "end_date": record.get("end_date"),
                "opened_at": record.get("opened_at"),
                "closed_at": record.get("closed_at"),
            })
        elif entity_type == "event":
            cache_record.update({
                "source": record.get("source"),
                "severity": record.get("severity"),
                "node": record.get("node"),
                "message_key": record.get("message_key"),
                "opened_at": record.get("opened_at"),
                "closed_at": record.get("closed_at"),
            })

        cache_records.append(cache_record)

    # Define columns to update on conflict
    # In a real scenario, this might be dynamic or defined on the model
    update_cols = [
        "external_modified_at", 
        "local_synced_at",
        "short_description", 
        "description", 
        "state"
    ]
    
    # Add entity specific update columns if needed
    if entity_type == "incident":
        update_cols.extend(["priority", "urgency", "impact", "assigned_to", "resolved_at", "closed_at"])
    elif entity_type == "change":
        update_cols.extend(["risk", "change_type", "assigned_to", "start_date", "end_date", "closed_at"])
    elif entity_type == "event":
        update_cols.extend(["severity", "node", "closed_at"])

    return bulk_upsert(
        db=db,
        model=model,
        records=cache_records,
        index_elements=["external_id"],
        update_columns=update_cols
    )


def reconcile_deletes(
    db: Session,
    entity_type: str,
    external_api_client: Any,
) -> int:
    """
    Reconcile soft-deleted records by fetching all active IDs from source.

    This is a periodic job (weekly) to catch records deleted in the source
    system that we may have missed via incremental sync.

    Args:
        db: Database session
        entity_type: Entity type to reconcile
        external_api_client: Client for calling external ITSM API

    Returns:
        Number of records marked as deleted
    """
    logger.info(f"Starting delete reconciliation for {entity_type}")

    model = CACHE_MODELS[entity_type]

    # Fetch all active IDs from source system
    active_ids = external_api_client.fetch_all_active_ids(entity_type=entity_type)
    active_ids_set = set(active_ids)

    # Find cached records not in active set
    cached_records = db.execute(
        select(model.external_id).where(model.is_deleted == False)
    ).scalars().all()

    deleted_ids = [
        record_id for record_id in cached_records
        if record_id not in active_ids_set
    ]

    if deleted_ids:
        # Mark as deleted
        db.execute(
            model.__table__.update()
            .where(model.external_id.in_(deleted_ids))
            .values(is_deleted=True, local_synced_at=datetime.utcnow())
        )
        db.commit()
        logger.info(f"Marked {len(deleted_ids)} {entity_type} records as deleted")

    return len(deleted_ids)


def get_sync_health(db: Session) -> dict:
    """
    Get health status of all sync jobs.

    Returns:
        Dictionary with health status per entity type
    """
    watermarks = db.execute(select(SyncWatermark)).scalars().all()

    health = {}
    for wm in watermarks:
        health[wm.entity_type] = {
            "status": wm.status,
            "last_success_at": wm.last_success_at.isoformat() if wm.last_success_at else None,
            "staleness_seconds": wm.staleness_seconds,
            "consecutive_failures": wm.consecutive_failures,
            "records_synced": wm.records_synced,
            "sync_duration_seconds": wm.sync_duration_seconds,
            "is_healthy": wm.is_healthy,
        }

    return health
