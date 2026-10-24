# Phase 1 architecture

FDR Guardian starts as a modular monolith. The React/Vite frontend calls a versioned FastAPI application. API routes remain separate from configuration and database connection helpers so later business logic and persistence can be added without splitting the deployment into services.

PostgreSQL is the intended database. The Compose file supplies a local PostgreSQL 17 service for development; the backend accepts its connection string through `DATABASE_URL`. Phase 1 checks connectivity with `SELECT 1` and creates no application tables. Schema changes will be introduced with migrations in a later phase.

The frontend's backend indicator calls `GET /api/v1/health`. A separate database health endpoint reports database reachability. No external AICTE system is connected. Future integration must use an authorised source behind a dedicated adapter, and any development records must be labelled synthetic.
