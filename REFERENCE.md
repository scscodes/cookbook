# Watermark-Based Cache Sync - Technical Reference

## Core Concept
We utilize a **Watermark** (`last_success_at`) to track the state of our synchronization with an external source of authority.

```
Watermark: 2024-01-15 14:20:00
API Call:  GET /incidents?modifiedSince=2024-01-15T14:20:00Z
Result:    Upsert 47 records → Update watermark to NOW()
```

## Database Schema

### Sync Watermarks (`sync_watermarks`)
Controls the state of the sync jobs. One row per entity type.

| Column | Type | Description |
|--------|------|-------------|
| `entity_type` | PK | `incident`, `change`, `event` |
| `last_success_at` | Timestamp | The "Watermark" for next API call |
| `status` | Enum | `success`, `failed`, `in_progress` |
| `consecutive_failures` | Int | Circuit breaker metric |

### Domain Caches (`incidents`, `changes`, `events`)
Local mirrors of external data. 
- **Identity**: `external_id` (PK) maps to Source UUID.
- **Sync Meta**: `external_modified_at`, `local_synced_at`.
- **Business Data**: `priority`, `state`, `risk`, etc.

## Sync Workflow (Infrastructure Layer)

1.  **Lock**: Attempt to acquire logical lock via `SyncWatermark.status`.
    *   *Fail Fast*: If status is `in_progress` and lock is fresh (<5m), abort.
2.  **Fetch**: Call `ExternalClient.fetch_modified_since(watermark)`.
3.  **Upsert**: Perform atomic UPSERT (Insert or Update) on `external_id`.
    *   *SQLite*: `INSERT OR REPLACE` / `ON CONFLICT DO UPDATE`
    *   *Postgres*: `INSERT ... ON CONFLICT DO UPDATE`
4.  **Commit**: Update Watermark timestamp and release lock.

## Domain Logic vs. Sync Logic

*   **Infrastructure (`app/infrastructure`)**: "Get the data here."
    *   Handles API auth, rate limits, database upserts, and scheduling.
    *   *Does not know* what "High Risk" means.
    
*   **Domain (`app/domain`)**: "Use the data."
    *   **Incident Service**: Calculates risk based on priority & state.
    *   **Change Service**: Identifies conflicts and emergency changes.
    *   **Event Service**: Correlates alerts to impact scores.
    *   *Does not know* about the sync scheduler or external API.

## Configuration & Deployment

### Runtime Switching
Controlled via `.env`:
*   `DB_TYPE=sqlite`: Uses `sqlite:///./app.db`. Enables WAL mode automatically for concurrency.
*   `DB_TYPE=postgres`: Uses standard connection pool.

### Startup Sequence
1.  **FastAPI Lifespan** triggers.
2.  `database.init_db()`: Checks/Creates tables.
3.  `scheduler.start()`: Loads jobs into APScheduler.

### Observability
*   **Health Endpoint**: `/api/v1/health/sync` returns status of all watermarks.
*   **Logs**: Stdout logging for sync start/finish and error traces.
