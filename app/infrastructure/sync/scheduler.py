"""
Scheduler configuration for periodic cache refresh jobs.

Uses APScheduler to run sync jobs on independent cadences per entity type.
Configure this in your FastAPI startup event or as a standalone service.
"""

import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.infrastructure.sync.manager import (
    reconcile_deletes,
    sync_entity,
)

logger = logging.getLogger(__name__)


class SyncScheduler:
    """
    Manages scheduled sync jobs for cache refresh.

    Runs on independent cadences per entity type and handles failure
    recovery automatically.
    """

    def __init__(
        self,
        db_session_factory: Any,  # Callable that returns a Session
        external_api_client: Any,  # Your external ITSM API client
    ):
        """
        Initialize the sync scheduler.

        Args:
            db_session_factory: Factory function that returns a new DB session
            external_api_client: Client for calling external ITSM API
        """
        self.db_session_factory = db_session_factory
        self.external_api_client = external_api_client
        self.scheduler = AsyncIOScheduler()

    def start(self) -> None:
        """
        Start the scheduler with all sync jobs configured.

        Call this during application startup (FastAPI lifespan event).
        """
        logger.info("Starting sync scheduler")

        # Incidents: Sync every 5 minutes
        self.scheduler.add_job(
            func=self._sync_incidents,
            trigger=IntervalTrigger(minutes=5),
            id="sync_incidents",
            name="Sync Incidents",
            replace_existing=True,
            max_instances=1,  # Prevent concurrent runs
        )

        # Changes: Sync every 15 minutes
        self.scheduler.add_job(
            func=self._sync_changes,
            trigger=IntervalTrigger(minutes=15),
            id="sync_changes",
            name="Sync Changes",
            replace_existing=True,
            max_instances=1,
        )

        # Events: Sync every 30 minutes
        self.scheduler.add_job(
            func=self._sync_events,
            trigger=IntervalTrigger(minutes=30),
            id="sync_events",
            name="Sync Events",
            replace_existing=True,
            max_instances=1,
        )

        # Delete reconciliation: Weekly on Sunday at 2 AM
        self.scheduler.add_job(
            func=self._reconcile_all_deletes,
            trigger="cron",
            day_of_week="sun",
            hour=2,
            minute=0,
            id="reconcile_deletes",
            name="Reconcile Deleted Records",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info("Sync scheduler started successfully")

    def shutdown(self, wait: bool = True) -> None:
        """
        Gracefully shut down the scheduler.

        Call this during application shutdown.

        Args:
            wait: If True, wait for running jobs to complete
        """
        logger.info("Shutting down sync scheduler")
        self.scheduler.shutdown(wait=wait)

    def _sync_incidents(self) -> None:
        """Sync incidents from external API."""
        self._run_sync("incident")

    def _sync_changes(self) -> None:
        """Sync changes from external API."""
        self._run_sync("change")

    def _sync_events(self) -> None:
        """Sync events from external API."""
        self._run_sync("event")

    def _run_sync(self, entity_type: str) -> None:
        """
        Execute sync for a single entity type.

        Handles database session lifecycle and error logging.

        Args:
            entity_type: Entity to sync (incident, change, event)
        """
        db = self.db_session_factory()
        try:
            records_synced = sync_entity(
                db=db,
                entity_type=entity_type,
                external_api_client=self.external_api_client,
            )
            logger.info(f"Sync completed for {entity_type}: {records_synced} records")
        except Exception as e:
            logger.error(f"Sync failed for {entity_type}: {e}", exc_info=True)
        finally:
            db.close()

    def _reconcile_all_deletes(self) -> None:
        """Reconcile soft-deleted records for all entity types."""
        db = self.db_session_factory()
        try:
            for entity_type in ["incident", "change", "event"]:
                deleted_count = reconcile_deletes(
                    db=db,
                    entity_type=entity_type,
                    external_api_client=self.external_api_client,
                )
                logger.info(
                    f"Delete reconciliation for {entity_type}: "
                    f"{deleted_count} records marked deleted"
                )
        except Exception as e:
            logger.error(f"Delete reconciliation failed: {e}", exc_info=True)
        finally:
            db.close()

    def get_job_status(self) -> dict:
        """
        Get current status of all scheduled jobs.

        Returns:
            Dictionary with job details and next run times
        """
        jobs = {}
        for job in self.scheduler.get_jobs():
            jobs[job.id] = {
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
        return jobs
