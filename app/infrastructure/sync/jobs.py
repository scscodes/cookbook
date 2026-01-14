from typing import Dict, List, Literal, NamedTuple, Optional

from apscheduler.triggers.base import BaseTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# Supported job types; extend if new types are introduced
JobType = Literal["incremental", "reconcile"]


class SyncJobDef(NamedTuple):
    """Declarative job definition for sync scheduling."""

    name: str
    entity_type: str
    trigger: BaseTrigger
    job_type: JobType = "incremental"
    params: Optional[Dict] = None


# Centralized registry of sync jobs and their schedules
REGISTERED_JOBS: List[SyncJobDef] = [
    SyncJobDef(
        name="Sync Incidents",
        entity_type="incident",
        trigger=IntervalTrigger(minutes=5),
        params={"label": "hot_incidents", "filters": {"states": ["new", "active", "in_progress"], "priority_max": 2}},
    ),
    SyncJobDef(
        name="Sync Incidents (Warm)",
        entity_type="incident",
        trigger=IntervalTrigger(minutes=60),
        params={"label": "warm_incidents", "filters": {"states": ["resolved", "closed"]}},
    ),
    SyncJobDef(
        name="Sync Changes",
        entity_type="change",
        trigger=IntervalTrigger(minutes=15),
    ),
    SyncJobDef(
        name="Sync Events",
        entity_type="event",
        trigger=IntervalTrigger(minutes=30),
    ),
    SyncJobDef(
        name="Reconcile Deleted Records",
        entity_type="all",
        trigger=CronTrigger(day_of_week="sun", hour=2, minute=0),
        job_type="reconcile",
    ),
]
