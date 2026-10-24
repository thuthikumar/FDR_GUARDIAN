# Synthetic data scenarios

Every row created by `python -m app.seed` is explicitly flagged synthetic. Institution names/codes, bank names, FDR numbers, email addresses, and release references are fictional. Emails use the reserved `.invalid` domain. `SCENARIO_RECORD_IDS` in `backend/app/seed.py` maps names to stable `internal_fdr_id` values for later tests and demonstrations.

The default reference date is the local current date. `--reference-date YYYY-MM-DD` shifts maturity scenarios relative to that date. A fixed Python random seed keeps the generated values reproducible. Re-running the seed upserts institutions by institution code, records by internal FDR ID, and users by email; child records use stable identifiers. Append-only approval and audit rows are inserted once and never rewritten.

| Scenario | Internal FDR IDs | Demonstration |
| --- | --- | --- |
| Valid-looking demo FDR | `SYN-FDR-0001` | Fictional certificate metadata and a reviewed synthetic field. This is not proof of document authenticity. |
| Upcoming maturity | `SYN-FDR-0002` | Maturity is 25 days after the reference date, with an open maturity alert. |
| Maturity in the past | `SYN-FDR-0003` | Maturity is 10 days before the reference date; a review alert is resolved. |
| Missing required document | `SYN-FDR-0004` | No document metadata row is present. |
| Amount mismatch | `SYN-FDR-0005` | Extracted synthetic amount differs from the stored amount. |
| FDR number mismatch | `SYN-FDR-0006` | Extracted synthetic FDR number differs from the stored number. |
| Maturity-date mismatch | `SYN-FDR-0007` | Extracted synthetic maturity date differs from the stored date. |
| Duplicate identifier | `SYN-FDR-0008`, `SYN-FDR-0009` | Two records in the same synthetic institution share one FDR number; neither is blocked by a uniqueness rule. |
| OCR uncertainty | `SYN-FDR-0009` | One extracted field has null confidence and another has low synthetic confidence. No authenticity claim is made. |
| Pending verification | `SYN-FDR-0010` | Submitted workflow case awaits review. |
| Additional information requested | `SYN-FDR-0011` | Case uses `more_information_required`. |
| Rejected with reason | `SYN-FDR-0012` | Rejected case and append-only action include a synthetic reason. |
| Approved without release | `SYN-FDR-0013` | Approval action exists and no release event exists. |
| Confirmed demo release | `SYN-FDR-0014` | Separate release event has `is_demo = true`; it represents no real transfer of funds. |

Document records are metadata only. Storage keys use the `synthetic/` prefix; no files are created in private storage until the document-upload phase. Seeded users have null `password_hash` values; authentication and development credentials belong to Phase 3.

## Inspecting the seeded data

From the project root, open a PostgreSQL shell in the Compose container:

```powershell
docker compose exec db psql -U fdr_guardian -d fdr_guardian
```

Useful read-only queries:

```sql
SELECT institution_code, institution_name, is_synthetic
FROM institutions ORDER BY institution_code;

SELECT internal_fdr_id, institution_id, fdr_number, maturity_date, verification_status, is_synthetic
FROM fdr_records WHERE internal_fdr_id BETWEEN 'SYN-FDR-0001' AND 'SYN-FDR-0014'
ORDER BY internal_fdr_id;

SELECT status, count(*) FROM verification_cases GROUP BY status ORDER BY status;
SELECT status, count(*) FROM alerts GROUP BY status ORDER BY status;
SELECT case_id, fdr_record_id, is_demo, released_at FROM release_events;
```
