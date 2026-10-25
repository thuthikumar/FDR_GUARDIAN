# FDR Guardian

FDR Guardian is an administrative platform foundation for managing institution-wise Fixed Deposit Receipt (FDR) and security deposit lifecycles, including document verification, maturity monitoring, discrepancies, approvals, notifications, and audit history.

The current milestone is **Phase 4: Institution Management and FDR CRUD**. The project contains a React/TypeScript registry UI, a FastAPI API, PostgreSQL schema managed with Alembic, backend-enforced permissions and institution scope, audit history, and clearly labelled synthetic development records. It does not connect to AICTE production systems or contain real institutional FDR records.

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

`.env` is excluded from Git. The example values are placeholders; replace them for local development. Generate a JWT secret with `py -c "import secrets; print(secrets.token_urlsafe(48))"` and put the output in `JWT_SECRET_KEY`. Keep `POSTGRES_PASSWORD` and the password portion of `DATABASE_URL` in sync. The frontend has its own `frontend/.env.example`; never put secrets in `VITE_` variables because those are bundled into browser code.

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

The backend reads `DATABASE_URL` from the project-level `.env`. Use matching credentials if you changed the Compose environment. The API listens at `http://127.0.0.1:8000`; interactive API documentation is at `http://127.0.0.1:8000/docs`.

## Apply the database migration

Run these commands from `backend/` after PostgreSQL is healthy:

```powershell
python -m alembic upgrade head
python -m alembic current
```

Alembic reads `DATABASE_URL` from the project `.env`; the URL is not stored in `alembic.ini`. Migrations create the Phase 2 data schema and the Phase 3 authentication fields, refresh-token table, and institution-admin constraint, along with their indexes and append-only audit triggers. To verify a local development rollback and re-apply:

```powershell
python -m alembic downgrade base
python -m alembic upgrade head
```

`downgrade base` drops the Phase 2 and Phase 3 schema and its data from the configured database. Use it only for a disposable local development database. The automated migration round-trip runs on the separate test database.

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

## Set local passwords for synthetic users

Set a local `SEED_DEV_PASSWORD` value in `.env` (at least 12 characters), then from `backend/` run:

```powershell
python -m app.db.set_dev_passwords
```

This development-only command sets Argon2id hashes for rows marked `is_synthetic=true`. It refuses to run in `APP_ENV=production`, without `SEED_DEV_PASSWORD`, or with the example placeholder. It never prints the password or hashes. It does not set passwords for administrator-created, non-synthetic users. Password reset, email verification, and administrator password provisioning are not implemented in this phase.

Synthetic demo login emails (all use the local `SEED_DEV_PASSWORD`; this README deliberately does not include any password):

- System administrator: `system-admin@synthetic.invalid`
- Institution administrators: `institution-001-admin@synthetic.invalid` through `institution-010-admin@synthetic.invalid`
- Verification officers: `verification-01@synthetic.invalid`, `verification-02@synthetic.invalid`
- Accounts officer: `accounts-01@synthetic.invalid`
- Final approver: `approver-01@synthetic.invalid`
- Read-only auditor: `auditor-01@synthetic.invalid`

## Test the login flow

1. Configure `.env` with `JWT_SECRET_KEY` (32+ random characters), `APP_ENV=development`, `COOKIE_SECURE=false`, `FRONTEND_ORIGIN=http://127.0.0.1:5173`, and `SEED_DEV_PASSWORD`.
2. Start PostgreSQL, apply migrations, seed synthetic records, and run `python -m app.db.set_dev_passwords` from `backend/`.
3. Start FastAPI on `http://127.0.0.1:8000` and the frontend on `http://127.0.0.1:5173`.
4. Sign in with any listed synthetic email and the local seed password. The access token stays in browser memory; the refresh token is an HttpOnly cookie.
5. Use Log out, then reload `/`. The protected route should return to `/login`. The Phase 1 system-status panel remains available on the login screen and in the authenticated app shell.

The permission mapping is a proposed application design and is not a verified AICTE role structure. Route guards in React are for user experience; all authentication and permissions are enforced by FastAPI. See [docs/phase-3-auth-rbac.md](docs/phase-3-auth-rbac.md) for the role matrix and authentication details, and [docs/phase-4-fdr-management.md](docs/phase-4-fdr-management.md) for registry endpoints, validation, status transitions, and history.

Health endpoints:

- `GET http://127.0.0.1:8000/api/v1/health` reports whether the API is running.
- `GET http://127.0.0.1:8000/api/v1/health/database` executes `SELECT 1` and reports `connected`, `unavailable`, or `not_configured`. It does not expose the database URL or exception details.

## Start the frontend

In another PowerShell terminal:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open `http://127.0.0.1:5173`. The page calls the backend health endpoint and displays the actual result. The default backend URL is `http://127.0.0.1:8000`; if the backend uses another URL, copy `frontend/.env.example` to `frontend/.env.local` and change `VITE_API_BASE_URL` there.

Run the frontend login and protected-route tests with:

```powershell
npm.cmd test
```

## Run backend tests

From the `backend` directory, with its virtual environment activated and PostgreSQL running:

```powershell
python -m pytest
```

The test suite uses `TEST_DATABASE_URL`, or derives a separate database name by appending `_test` to `DATABASE_URL`. The fixture refuses any database whose name does not end in `_test` or matches `DATABASE_URL`, before it can create, migrate, or clear anything. If the test database does not exist, the fixture creates it, so the configured database user needs permission to create databases. At session start, tests reset only that dedicated test database and apply migrations. Never point `TEST_DATABASE_URL` at production or at the development database.

Backend tests cover health responses, migration upgrade/downgrade/upgrade, schema constraints, synthetic seed scenarios and idempotency, authentication, lockout and refresh rotation, registry validation, CRUD, permissions, institution isolation, user administration, and audit behavior. Frontend tests cover login validation, protected-route redirects, registry form validation, list pagination, and error states.
