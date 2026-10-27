# Phase 3: Authentication, Roles, and Record-Level Authorisation

Phase 3 adds password login, short-lived access JWTs, rotating refresh cookies, backend permission dependencies, institution-scoped FDR query helpers, minimal user administration, and security audit events. The permission mapping below is a **proposed application design**. It is not a verified representation of AICTE's actual internal roles or organisation.

All demo accounts and records are synthetic. The application has no access to AICTE production systems, APIs, or real FDR records.

## Permission matrix

| Role | Permissions |
| --- | --- |
| `system_admin` | `user.manage`, `audit.read`, `institution.read`, `institution.write`, `fdr.read`, `alert.read`, `alert.manage`, `monitoring.run`, `monitoring.configure`, `case.read`, `report.read`, `integration.manage` |
| `institution_admin` | `institution.read`, `fdr.read`, `fdr.write`, `document.upload`, `document.read`, `case.read`, `alert.read`, `report.read` |
| `verification_officer` | `institution.read`, `fdr.read`, `document.read`, `document.reprocess`, `extraction.review`, `case.read`, `case.review`, `alert.read`, `alert.manage`, `report.read` |
| `accounts_officer` | `institution.read`, `fdr.read`, `case.read`, `case.financial_review`, `release.record`, `alert.read`, `report.read`, `report.export` |
| `final_approver` | `institution.read`, `fdr.read`, `document.read`, `case.read`, `case.approve`, `alert.read`, `report.read` |
| `read_only_auditor` | `institution.read`, `fdr.read`, `document.read`, `case.read`, `alert.read`, `audit.read`, `report.read`, `report.export` |

`read_only_auditor` has no write permission. `institution.write` is granted only to `system_admin`; it enables institution registry management in Phase 4. `alert.manage` is granted to Verification Officers and System Administrators. `monitoring.run` and `monitoring.configure` are restricted to System Administrators. These permissions are enforced by FastAPI dependencies; React route guards only improve the user experience. Phase 3 implements a protected `/api/v1/admin/users` surface and auth routes. The Phase 5 dashboard and read-only report endpoints reuse `report.read`; CSV exports additionally require `report.export`, held by Accounts Officers and Read-only Auditors. These report endpoints never modify FDR, case, or alert rows.

Phase 7 adds private document APIs. `document.upload` remains institution-administrator-only and is scoped to the user's institution. `document.read` is granted to Institution Administrators, Verification Officers, Final Approvers, and Read-only Auditors. `document.reprocess` is granted only to Verification Officers. System Administrators do not receive document access. Reprocessing is a machine extraction action and refuses any document with reviewer-confirmed values.

## Token and cookie design

1. `POST /api/v1/auth/login` accepts an email and password. Passwords are verified with Argon2id. The response body contains a short-lived access JWT.
2. The response also sets a cryptographically random refresh token in an HttpOnly, `SameSite=Strict` cookie with path `/api/v1/auth`. `COOKIE_SECURE=false` is the local development setting; production refuses to start unless `COOKIE_SECURE=true`.
3. The database stores only the SHA-256 hash of each random refresh token, its family ID, expiry, revocation time, and replacement row ID. The raw refresh token is never stored. Refresh tokens expire after seven days by default and rotate on each successful `POST /api/v1/auth/refresh`.
4. A just-rotated token may be presented concurrently for a configurable 10-second grace period (`REFRESH_TOKEN_REUSE_GRACE_SECONDS`); this succeeds only while its replacement remains active. Reuse after that window revokes all still-active tokens in the family and writes a `token_reuse_detected` audit event.
5. `POST /api/v1/auth/logout` revokes the presented refresh token and clears the cookie. `GET /api/v1/auth/me` returns only user identity, role, institution ID, and permissions.

The frontend keeps the access JWT in memory only. On page load it attempts `/auth/refresh`, then loads `/auth/me`. An API 401 triggers one refresh attempt; if that fails the in-memory session is cleared and the protected route redirects to login. No access token is written to local or session storage.

Configure the backend environment:

```dotenv
APP_ENV=development
JWT_SECRET_KEY=<random value with at least 32 characters>
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
REFRESH_TOKEN_REUSE_GRACE_SECONDS=10
COOKIE_SECURE=false
FRONTEND_ORIGIN=http://127.0.0.1:5173
SEED_DEV_PASSWORD=<local synthetic-user password>
```

`JWT_SECRET_KEY` has no application default. Startup fails if it is missing, shorter than 32 characters, or still a recognizable example placeholder. Production requires `COOKIE_SECURE=true`. CORS allows credentials from the one configured `FRONTEND_ORIGIN` and the API's GET, POST, and PATCH methods.

## Passwords and account lockout

The login error is the same for an unknown account, a wrong password, an inactive user, and a locked account. Unknown users still incur Argon2id verification work using a process-local dummy hash. Five consecutive failures lock a user for 15 minutes. A successful login resets the counter and lock.

Seeded users have no password hash until a developer opts in. From `backend/`, with `SEED_DEV_PASSWORD` set in the local `.env`, run:

```powershell
python -m app.db.set_dev_passwords
```

The command refuses to run in production, without the password variable, or with its placeholder. It updates only users where `is_synthetic=true` and prints only the number updated. Do not commit `.env` or put passwords in documentation, command history, or logs.

## Institution isolation

Only `institution_admin` is restricted to the `institution_id` on their user account. FDR query helpers automatically filter their queries to that institution. A request for another institution's FDR returns 404, the same response as a missing record, so the other institution's record existence is not disclosed. Other proposed roles are global. This policy is implemented in backend helpers and must be applied by future record endpoints; frontend hiding is not a security boundary.

Phase 5 applies the same institution filter to dashboard metrics, chart aggregates, institution summaries, maturity rows, and CSV exports. A requested other-institution filter from an institution administrator is ignored in favor of the administrator's own institution scope.

## User administration

The `user.manage` permission protects:

- `GET /api/v1/admin/users`
- `POST /api/v1/admin/users`
- `PATCH /api/v1/admin/users/{id}` for role, active status, and institution assignment

Institution administrators must have an institution ID; the database also enforces this rule. User API responses omit `password_hash`. New administrator-created accounts have no password provisioning flow in Phase 3 and cannot log in until a future approved provisioning or password-reset flow exists.

## Audit and request correlation

An `X-Request-ID` middleware accepts a bounded safe request ID or generates a UUID, and returns it in the response header. The audit service stores it as `audit_events.correlation_id`.

Events include login success/failure, account lockout, logout, refresh-token reuse, user creation, role change, institution assignment change, and deactivation. Authentication failures never include the submitted password. The audit service drops summary keys containing password, token, secret, hash, or API-key terms. Existing database triggers keep audit events append-only.

## Tests and known limitations

Backend tests require PostgreSQL and a dedicated database name ending in `_test`, distinct from `DATABASE_URL`. The fixture validates this before creating, migrating, or truncating any database. Tests cover migrations, Argon2id, auth flows, lockout, refresh rotation/reuse, role permissions, institution isolation, admin audit, and synthetic-only password setup. Frontend tests use Vitest and Testing Library for login validation/errors and protected-route redirects.

Known limitations: no MFA, password reset, email verification, administrator password provisioning, per-IP rate limit, HTTPS deployment, or production identity integration is implemented. This phase defines the proposed permission design; it is not an AICTE-approved access model. Use synthetic data only.
