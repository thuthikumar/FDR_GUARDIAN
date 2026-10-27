# Phase 4: Institution Management and FDR CRUD

Phase 4 adds the institution registry and the first institution-scoped FDR management API and UI. All development and demo records are synthetic. The application has no access to AICTE production data, APIs, or real FDR records.

## Permissions and scope

`institution.write` is granted only to `system_admin`. The other Phase 3 role permissions are unchanged. Institution registry reads use `institution.read`; FDR reads use `fdr.read`; FDR writes use `fdr.write`. Institution administrators are scoped to their assigned institution on every institution and FDR read, edit, status, and history endpoint. Cross-institution details return 404. A requested institution filter on an institution administrator's FDR list is ignored; a mismatched institution on create returns 403.

## Endpoints

All routes use the `/api/v1` prefix, require authentication, and return Pydantic schemas rather than ORM objects.

| Method | Route | Permission | Purpose |
| --- | --- | --- | --- |
| GET | `/institutions` | `institution.read` | Paginated institution search, status/state filters, whitelisted sort |
| GET | `/institutions/{institution_id}` | `institution.read` | Institution fields and FDR count, active count, principal total, nearest upcoming maturity |
| POST | `/institutions` | `institution.write` | Create synthetic institution; duplicate code returns 409 |
| PATCH | `/institutions/{institution_id}` | `institution.write` | Edit institution fields, including status-based deactivation |
| GET | `/fdrs` | `fdr.read` | Paginated search, filters, and whitelisted sort |
| GET | `/fdrs/{record_id}` | `fdr.read` | Read one scoped record |
| POST | `/fdrs` | `fdr.write` | Create a scoped manual-entry record |
| PATCH | `/fdrs/{record_id}` | `fdr.write` | Edit allowed business fields using optimistic `updated_at` concurrency |
| POST | `/fdrs/{record_id}/status` | `fdr.write` | Change record status with required remarks |
| GET | `/fdrs/{record_id}/history` | `fdr.read` | Read that record's history without requiring general `audit.read` |

There are no institution or FDR DELETE routes. List page sizes are 1–100. Sort fields are explicit API allowlists; search treats `%` and `_` as literal characters.

## FDR validation and create/update rules

- Amount must be greater than zero, fit the database `NUMERIC(14,2)` column, and have no more than two decimal places.
- Currency is exactly three uppercase letters and defaults to `INR`.
- Maturity must be after issue date. Issue date may be at most one day in the future to accommodate local date-boundary differences.
- Bank name is trimmed, nonblank, and at most 160 characters; branch name is at most 160; FDR number is trimmed, nonblank, and at most 100.
- `internal_fdr_id`, initial `draft` status, `not_submitted` verification state, and `MANUAL_ENTRY` source are assigned by the server. Development-created rows are marked synthetic. Repeated FDR numbers are allowed.
- PATCH accepts only bank name, branch name, FDR number, amount, currency, issue date, maturity date, and the required timezone-aware `updated_at`. Protected fields and unknown properties return 422. A stale `updated_at` returns 409.
- Every successful create, edit, or status change writes field-level old/new values and actor metadata to `audit_events` in the same transaction as the record change. Status remarks are stored with the event; no secrets are included.

## Record status transitions

Transitions derive from `FDRRecordStatus`; verification workflow state is not modified by these endpoints.

| Current status | Allowed next statuses |
| --- | --- |
| `draft` | `active`, `cancelled` |
| `active` | `matured`, `cancelled` |
| `matured` | `released` |
| `released` | None (terminal) |
| `cancelled` | None (terminal) |

Disallowed transitions return 409. Every status change requires nonblank remarks (maximum 1,000 characters). `released` means the existing status was recorded; this endpoint does not prove funds release or implement the future authorised release workflow.

## History

History reads only `audit_events` for the requested `fdr_record` entity and the three FDR registry write actions. Each entry includes actor display name, timestamp, changed-field old/new values, and optional remarks. The record is scoped through the same FDR visibility helper before its events are read; this endpoint does not grant access to the general audit log.

## Frontend

The authenticated app shell provides Institutions and FDR Registry navigation, filtered by the user's permissions. Lists include search/filter/pagination; detail views include institution statistics or record history and permitted actions. FDR forms use React Hook Form and Zod and mirror backend validation. Money uses INR formatting and dates use `en-IN`. The Phase 1 API health panel remains reachable. Frontend guards are for usability; FastAPI enforces permissions and institution scope.

## Known boundaries

This phase does not implement workflow approvals, verification-state changes, documents/OCR, alerts, dashboards/charts, reporting, CSV import, or FDR deletion. No production integration is configured. The Phase 1 panel checks API liveness at `/api/v1/health`; the separate database connectivity endpoint is `/api/v1/health/database`.
