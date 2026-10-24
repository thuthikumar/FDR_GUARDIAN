# FDR Guardian

FDR Guardian is an administrative platform foundation for managing institution-wise Fixed Deposit Receipt (FDR) and security deposit lifecycles, including document verification, maturity monitoring, discrepancies, approvals, notifications, and audit history.

The current milestone is **Phase 2: Database Schema, Migrations, and Synthetic Data**. The project contains a React/TypeScript landing page, a FastAPI foundation, PostgreSQL schema managed with Alembic, and clearly labelled synthetic development records. It does not connect to AICTE production systems or contain real institutional FDR records.

## Prerequisites

- Python 3.11 or newer (developed with Python 3.14)
- Node.js 20.19+ or 22.12+ and npm (developed with Node 26)
- Git
- PostgreSQL 16+ **or** Docker Desktop with Docker Compose for the included PostgreSQL service

If PowerShell blocks `npm.ps1` due to execution policy, use `npm.cmd` in the commands below.

## Project layout

```text
fdr-guardian/
├── backend/
│   ├── app/
│   │   ├── api/       # Versioned HTTP routes
│   │   ├── core/      # Environment-backed configuration
│   │   ├── db/        # Base, session, constraints, connectivity
│   │   ├── models/    # SQLAlchemy domain models and shared enums
│   │   └── seed.py    # Deterministic synthetic data command
│   ├── migrations/    # Alembic environment and revisions
│   ├── tests/         # API, schema, migration, and seed tests
│   ├── alembic.ini
│   └── requirements.txt
├── frontend/
│   └── src/           # React application and styles
├── docs/              # Architecture, schema, and synthetic-data notes
├── compose.yaml       # Optional local PostgreSQL service
├── .env.example       # Placeholder development configuration
└── README.md
```

## Configure environment

From this directory, create a local environment file:

```powershell
Copy-Item .env.example .env
```

`.env` is excluded from Git. The example password is a placeholder for local development; replace it before using any shared or deployed environment. Keep `POSTGRES_PASSWORD` and the password portion of `DATABASE_URL` in sync. The frontend has its own `frontend/.env.example`; never put secrets in `VITE_` variables because those are bundled into browser code.

## Start PostgreSQL

Docker Desktop is optional if PostgreSQL is already installed and available on port 5432. Otherwise, start Docker Desktop, then from this directory run:

```powershell
docker compose up -d db
docker compose ps
```

The Compose service uses `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` from `.env`. To stop it, run `docker compose down`; data remains in a named Docker volume. To remove that local database volume as well, run `docker compose down -v`.

## Start the backend

In a PowerShell terminal:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

The backend reads `DATABASE_URL` from the project-level `.env`. Use matching credentials if you changed the Compose environment. The API listens at `http://localhost:8000`; interactive API documentation is at `http://localhost:8000/docs`.

## Apply the database migration

Run these commands from `backend/` after PostgreSQL is healthy:

```powershell
python -m alembic upgrade head
python -m alembic current
```

Alembic reads `DATABASE_URL` from the project `.env`; the URL is not stored in `alembic.ini`. The migration creates the Phase 2 tables, constraints, indexes, and append-only triggers. To verify a local development rollback and re-apply:

```powershell
python -m alembic downgrade base
python -m alembic upgrade head
```

`downgrade base` drops the Phase 2 schema and its data from the configured database. Use it only for a disposable local development database. The automated migration round-trip runs on the separate test database.

## Seed synthetic data

From `backend/`, with the virtual environment active and the development migration applied:

```powershell
python -m app.seed
```

The seed is deterministic and idempotent. It creates 10 fictional institutions, 100 synthetic FDR records, synthetic users, metadata-only document rows, workflow examples, alerts, audit events, and a synchronization record. Dates use today's date by default; supply a stable reference date when needed:

```powershell
python -m app.seed --reference-date 2026-10-24
```

No document files are written. Placeholder storage keys begin with `synthetic/`. All user emails use `@synthetic.invalid`, and seeded password hashes remain null. See [docs/synthetic-data.md](docs/synthetic-data.md) for scenario details and IDs.

Health endpoints:

- `GET http://localhost:8000/api/v1/health` reports whether the API is running.
- `GET http://localhost:8000/api/v1/health/database` executes `SELECT 1` and reports `connected`, `unavailable`, or `not_configured`. It does not expose the database URL or exception details.

## Start the frontend

In another PowerShell terminal:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open `http://127.0.0.1:5173`. The page calls the backend health endpoint and displays the actual result. The default backend URL is `http://localhost:8000`; if the backend uses another URL, copy `frontend/.env.example` to `frontend/.env.local` and change `VITE_API_BASE_URL` there.

## Run backend tests

From the `backend` directory, with its virtual environment activated and PostgreSQL running:

```powershell
python -m pytest
```

The test suite uses `TEST_DATABASE_URL`, or derives a separate database name by appending `_test` to `DATABASE_URL`. It never runs schema changes or seed data against the development database. If that test database does not exist, the fixture creates it, so the configured database user needs permission to create databases. At session start, tests reset only that dedicated test database and apply migrations. Never point `TEST_DATABASE_URL` at production or at the development database.

Phase 2 tests cover health responses, migration upgrade/downgrade/upgrade, schema constraints, synthetic seed scenarios and idempotency, duplicate identifier behavior, active-alert uniqueness, and database-enforced audit immutability.
