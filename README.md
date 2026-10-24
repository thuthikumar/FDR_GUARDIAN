# FDR Guardian

FDR Guardian is an administrative platform foundation for managing institution-wise Fixed Deposit Receipt (FDR) and security deposit lifecycles, including document verification, maturity monitoring, discrepancies, approvals, notifications, and audit history.

The current milestone is **Phase 1: Foundation and Environment Setup**. It contains a React/TypeScript landing page and a FastAPI backend with API and PostgreSQL health checks. The project does not connect to AICTE production systems or contain real institutional FDR records. Future sample records will be labelled synthetic.

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
│   │   └── db/        # Database connectivity helpers
│   ├── tests/         # API health tests
│   └── requirements.txt
├── frontend/
│   └── src/           # React application and styles
├── docs/              # Architecture notes
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

From the `backend` directory, with its virtual environment activated:

```powershell
python -m pytest
```

The tests cover the API health response and the database check's unconfigured response. They do not require a running PostgreSQL server.
