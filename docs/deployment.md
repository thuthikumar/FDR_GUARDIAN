# Demo deployment guide

This is a **synthetic-data demo**. It contains no AICTE data, has no AICTE or government-system integration, and makes no production-readiness or production-use claims. Use it only with synthetic records and demo accounts.

The target layout is Neon PostgreSQL, a Docker web service on Render, and the Vite frontend on Vercel. The backend image installs Tesseract OCR and English language data, runs as UID 10001, applies Alembic migrations before starting Uvicorn, and does not seed data on startup. Render receives only the environment variables listed below.

## 1. Create the Neon database

1. Create a Neon project and a database/role for this demo.
2. In Neon Console choose **Connect**, select the database and role, and copy the connection string. Neon supplies a PostgreSQL URI with TLS parameters such as `sslmode=require` (and may include `channel_binding=require`). Store the complete URI as `DATABASE_URL` in Render. The app converts Neon’s standard `postgresql://` scheme to SQLAlchemy’s installed `psycopg` 3 driver while preserving query parameters.
3. Use the pooled connection string Neon provides by default unless direct connections are specifically needed. Never commit the URL or put it in a frontend variable.

Neon describes the connection URI and its TLS parameters in [Connect from any application](https://neon.com/docs/connect/connect-from-any-app).

## 2. Deploy the backend to Render

1. Create a **Web Service** from this repository and select **Docker**.
2. Set the Docker build context to the repository root and Dockerfile Path to `./backend/Dockerfile`. The root `.dockerignore` excludes local environments, secrets, caches, and storage from the image build context.
3. Set the health check path to `/api/v1/health`.
4. A Render Free web service has no persistent disk; uploaded files on its ephemeral filesystem are lost on restart, redeploy, or spin-down. For persistent uploads, use a paid service with a disk mounted at `/var/data` and set `STORAGE_ROOT=/var/data`. The app validates that this directory is writable before applying migrations. Uploaded files are kept outside the `/app` web/code root and are served only through authorized API endpoints. See [Render free service limitations](https://render.com/docs/free) and [persistent disk limitations](https://render.com/docs/disks#disk-limitations-and-considerations).
5. Set the backend environment variables in the table below. Set `FRONTEND_ORIGIN` to the exact Vercel origin (scheme and host only, no path or trailing slash), for example `https://your-demo.vercel.app`.
6. Deploy. The non-root container validates production configuration and storage access, runs `python -m alembic upgrade head`, and only then starts Uvicorn on Render’s `$PORT`.
7. Check `https://<render-service>.onrender.com/api/v1/health` and confirm it returns HTTP 200. `/api/v1/docs`, `/api/v1/redoc`, and `/api/v1/openapi.json` are disabled in production.

Render’s [Docker instructions](https://render.com/docs/docker) cover selecting Docker and setting a Dockerfile path; its [health check guide](https://render.com/docs/health-checks) describes configuring an HTTP path. A Render persistent disk preserves data only under its mount path. It is attached to one service instance, prevents scaling that service to multiple instances, is unavailable to builds, pre-deploy commands, and one-off jobs, and disables zero-downtime deploys. Plan for a brief interruption during deploys and keep a separate backup of important uploaded demo files. See [Render persistent disk limitations](https://render.com/docs/disks#disk-limitations-and-considerations).

## 3. Seed the synthetic demo once

Seeding is never automatic. After the backend has deployed and its migrations have completed:

1. On a paid Render service, open the running instance’s **Shell**. Free services do not provide Shell access. Do not use a separate one-off job: a job cannot access the service’s attached disk.
2. Set `SEED_DEMO_PASSWORD` in that shell session to a unique password of at least 12 characters. Do not add it as a permanent Render environment variable.
3. Run:

   ```sh
   python -m app.db.seed_demo
   ```

The command requires `APP_ENV=production`, a valid `DATABASE_URL`, a non-placeholder `JWT_SECRET_KEY`, and `SEED_DEMO_PASSWORD`. It creates only explicitly synthetic fixture rows and sets that password only for users marked `is_synthetic`. The seed is deterministic and idempotent; it creates metadata-only document fixture rows and does not write uploaded files. Do not run this against any database containing non-demo data.

To rotate the shared demo-user password, set a new `SEED_DEMO_PASSWORD` temporarily in the running service’s shell and run:

```sh
python -m app.db.set_demo_passwords
```

This updates passwords for synthetic users only. Clear the shell variable when done. A shared demo password is intended only for a restricted demonstration; distribute it only to demo participants and rotate it after the demo.

## 4. Deploy the frontend to Vercel

1. Import the repository into Vercel and set **Root Directory** to `frontend`.
2. Use build command `npm run build` and output directory `dist`.
3. In `frontend/vercel.json`, replace `YOUR-RENDER-SERVICE` in the `/api/(.*)` rewrite destination with the actual Render service hostname, keeping `/api/$1`. The API rewrite is before the SPA fallback. Requests remain on the Vercel origin in the browser, so refresh cookies remain same-origin. The API rewrite explicitly disables Vercel rewrite caching.
4. Leave `VITE_API_BASE_URL` unset in production. The build uses relative `/api/v1` by default in `frontend/src/config/api.ts`, so API calls go through the same-origin Vercel rewrite and refresh cookies remain same-origin. If explicitly configured, use `/api/v1`.
5. Leave `VITE_SHOW_GOV_BRANDING` unset in production and for any public link. Its unset mode is neutral; only the case-insensitive string `true` enables government branding.
6. Set the Render `FRONTEND_ORIGIN` to the exact production Vercel origin. If using a Vercel preview, update the origin deliberately before testing preview sign-in; CORS allows exactly one configured origin.

Vercel documents [external rewrites](https://vercel.com/docs/routing/rewrites) and the [Vite project settings](https://vercel.com/docs/frameworks/frontend/vite). The static external rewrite destination lives in `frontend/vercel.json`; it is not read from a Vite variable.

## Environment variables

| Variable | Set on | Required/value | Purpose |
| --- | --- | --- | --- |
| `DATABASE_URL` | Render | Required in production; optional in development; no default | Neon `postgresql://...?...sslmode=require` URI, normalized for SQLAlchemy |
| `JWT_SECRET_KEY` | Render | Required at startup; no default; at least 32 characters and not a placeholder | Signs access and refresh tokens |
| `FRONTEND_ORIGIN` | Render | Required in production; HTTPS origin with no path; local default `http://127.0.0.1:5173` | Sole permitted CORS origin |
| `COOKIE_SECURE` | Render | Production required `true`; default `false` outside production | Requires Secure, HttpOnly, SameSite=Strict refresh cookies |
| `APP_ENV` | Render | Default `development`; production must set `production`; allowed values are exactly `development`, `test`, `production` | Enables production validation and disables API schema/docs |
| `STORAGE_ROOT` | Render | Optional; default `backend/storage`; set `/var/data` when using a disk | Private document storage |
| `TESSERACT_CMD` | Render | Optional; omit when `tesseract` is on `PATH` | Explicit executable path override |
| `PORT` | Render | Supplied by Render | Uvicorn listen port; falls back to 8000 for local container runs |
| `SEED_DEMO_PASSWORD` | Render shell, temporarily | Required for the one-off seed or password rotation; 12+ characters | Sets the password for synthetic accounts only; do not store as a service variable |
| `VITE_API_BASE_URL` | Vercel | Optional; default `/api/v1` | Same-origin API prefix sent through the Vercel rewrite |
| `VITE_SHOW_GOV_BRANDING` | Vercel | Optional; unset default is neutral; only `true` (case-insensitive) enables government identity | Branding mode |

The backend configuration also reads the following optional tuning, test, and OCR variables. Defaults apply when omitted. `TEST_DATABASE_URL` is only for tests and must point to a separate database ending in `_test`.

| Variable | Required/optional and default | Purpose |
| --- | --- | --- |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Optional; `15` | Access token lifetime |
| `APP_TIMEZONE` | Optional; `Asia/Kolkata` | Monitoring schedule timezone |
| `MATURITY_URGENT_DAYS` | Optional; `7` | Demo alert thresholds |
| `MATURITY_ATTENTION_DAYS` | Optional; `30` | Demo alert thresholds |
| `MATURITY_UPCOMING_DAYS` | Optional; `90` | Demo alert thresholds |
| `MAX_DOCUMENTS_PER_FDR` | Optional; `20` | Upload limit per FDR |
| `MAX_PDF_PAGES` | Optional; `10` | PDF processing limit |
| `MAX_UPLOAD_MB` | Optional; `10` | Upload size limit |
| `MONITORING_RUN_HOUR` | Optional; `2` | Scheduler run time |
| `MONITORING_RUN_MINUTE` | Optional; `0` | Scheduler run time |
| `OCR_ENABLED` | Optional; `true` | Enables OCR extraction |
| `OCR_LANGUAGES` | Optional; `eng` | Tesseract languages |
| `OCR_TIMEOUT_SECONDS` | Optional; `60` | OCR timeout |
| `PROCESSING_STALE_MINUTES` | Optional; `15` | Stale processing threshold |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Optional; `7` | Refresh token lifetime |
| `REFRESH_TOKEN_REUSE_GRACE_SECONDS` | Optional; `10` | Concurrent refresh grace period |
| `SCHEDULER_ENABLED` | Optional; `false` | Enables in-process monitoring scheduler |
| `TEST_DATABASE_URL` | Optional; unset | Isolated database URL for tests |

`PORT` is supplied by Render (container fallback `8000`). `SEED_DEMO_PASSWORD` has no default and is read by the one-off seed and password-rotation scripts from the running service shell; do not store it as a permanent service variable.

Production startup fails if the signing secret is missing, short, or a known placeholder; if the PostgreSQL URL is missing, malformed, or a placeholder; or if secure cookies are disabled. The application uses environment variables for production configuration. `.env` files are local-only, ignored by Git and excluded from the Docker context. Never put secrets in `VITE_*` variables.

## Security and operations

- CORS credentials are enabled only for `FRONTEND_ORIGIN`; wildcard origins are not used.
- `/docs`, `/redoc`, and `/openapi.json` are disabled when `APP_ENV=production`.
- The backend runs as a non-root user. Upload bytes live under `STORAGE_ROOT`, outside the served frontend and backend code roots.
- The production refresh cookie is Secure, HttpOnly, and SameSite=Strict; a backend test checks the Secure flag.
- Migrations run on each container start, before Uvicorn serves requests. Seed commands are separate and explicit.
- The Vercel API rewrite disables caching so authenticated API responses are not cached at the proxy.
- The frontend package does not currently include ESLint or an ESLint configuration, so there is no lint script. This is a known tooling gap; no lint script was added.

## Rollback

For an application regression, use Render’s previous successful deploy and Vercel’s previous deployment to restore the prior app revision. Database migrations are applied before the new app starts; review migration reversibility before deploying schema changes. Do not assume that rolling back the container reverses a migration. Preserve the Neon database and Render disk when rolling back, and restore them only from a deliberate backup procedure.

## Scope

This is a synthetic-data demo only. It contains no AICTE data, is not connected to AICTE or any government system, and does not support claims about production security, availability, compliance, or operational suitability.
