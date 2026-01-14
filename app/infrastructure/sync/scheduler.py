"""
Scheduler configuration for periodic cache refresh jobs.

Uses APScheduler to run sync jobs on independent cadences per entity type.
Configure this in your FastAPI startup event or as a standalone service.
"""

import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.infrastructure.sync.jobs import REGISTERED_JOBS
from app.infrastructure.sync.manager import reconcile_deletes, sync_entity

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
        for job_def in REGISTERED_JOBS:
            job_func = self._get_job_function(job_def.job_type)
            job_id = f"{job_def.job_type}_{job_def.entity_type}"

            self.scheduler.add_job(
                func=job_func,
                trigger=job_def.trigger,
                args=[job_def.entity_type, job_def.params],
                id=job_id,
                name=job_def.name,
                replace_existing=True,
                max_instances=1,
            )
            logger.info(f"Registered job: {job_def.name} ({job_def.trigger})")

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

    def _get_job_function(self, job_type: str):
        """Map job type to handler."""
        if job_type == "reconcile":
            return self._run_reconciliation
        return self._run_incremental_sync

    def _run_incremental_sync(self, entity_type: str, params: dict | None = None) -> None:
        """Generic handler for incremental syncs."""
        db = self.db_session_factory()
        try:
            records_synced = sync_entity(
                db=db,
                entity_type=entity_type,
                external_api_client=self.external_api_client,
                params=params,
            )
            logger.info(f"Sync completed for {entity_type}: {records_synced} records")
        except Exception as e:
            logger.error(f"Sync failed for {entity_type}: {e}", exc_info=True)
        finally:
            db.close()

    def _run_reconciliation(self, entity_type: str, params: dict | None = None) -> None:
        """Generic handler for reconciliation jobs."""
        targets = ["incident", "change", "event"] if entity_type == "all" else [entity_type]

        db = self.db_session_factory()
        try:
            for target in targets:
                deleted_count = reconcile_deletes(
                    db=db,
                    entity_type=target,
                    external_api_client=self.external_api_client,
                )
                logger.info(
                    f"Delete reconciliation for {target}: "
                    f"{deleted_count} records marked deleted"
                )
        except Exception as e:
            logger.error("Delete reconciliation failed", exc_info=True)
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
