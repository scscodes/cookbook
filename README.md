# Cookbook: Watermark Cache Sync POC

An architectural Proof of Concept demonstrating a "Single Pane of Glass" dashboard powered by a high-performance local cache of external ITSM data.

## The Problem
Enterprise ITSM APIs (ServiceNow, Jira, etc.) often have high latency (2-10s per call). Building a dashboard that aggregates data from multiple modules (Incidents, Changes, Events) results in unacceptable load times (>30s) and poor user experience.

## The Solution
A **Watermark-based Incremental Sync** architecture that:
1.  **Mirrors** external data into a local database (SQLite/PostgreSQL).
2.  **Decouples** user reads from external API latency.
3.  **Enables** complex cross-domain business logic (e.g., Risk Analysis) in milliseconds.

## Key Features
- **Incremental Sync**: Only fetches what changed since the last run.
- **Domain-Driven Design**: Business logic is separated from sync plumbing.
- **Unified Dashboard**: Aggregates Incidents, Changes, and Events in <200ms.
- **Runtime Flexibility**: switch between SQLite (Edge/POC) and PostgreSQL (Production) via `.env`.

## Architecture

For a detailed breakdown of the synchronization process and data flow, see [Synchronization Architecture](docs/sync_architecture.md).

```
app/
├── core/                  # Config & Database connection
├── domain/                # Business Logic (Risk, Impact analysis)
│   ├── incidents/
│   ├── changes/
│   └── events/
├── infrastructure/        # Plumbing
│   ├── external/          # Mock ITSM Adapter
│   ├── persistence/       # DB Ops & Models
│   └── sync/              # Scheduler & Sync Manager
└── interfaces/            # API Layer
    └── api/v1/            # Routers
```

## Getting Started

### 1. Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration
Copy the example config to active config:
```bash
cp .env.example .env
```
*Default is SQLite. To use Postgres, edit `.env` and set `DB_TYPE=postgres`.*

### 3. Run the App
```bash
uvicorn app.main:app --reload
```
*The app will automatically initialize the database and start the sync scheduler.*

## How to Demo

1.  **Populate Data**:
    If the cache is empty, force an immediate sync:
    ```bash
    curl -X POST http://localhost:8000/api/v1/admin/sync/incident
    curl -X POST http://localhost:8000/api/v1/admin/sync/change
    curl -X POST http://localhost:8000/api/v1/admin/sync/event
    ```

2.  **View the "Single Pane of Glass"**:
    Visit `http://localhost:8000/api/v1/dashboard/overview`
    *   *Observation*: Instant response aggregating critical stats across all domains.

3.  **Analyze Risk**:
    Pick an Incident ID from the list and check its risk score:
    `GET /api/v1/incidents/{id}/risk`

## License
MIT
