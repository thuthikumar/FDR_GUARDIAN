# FDR GUARDIAN
## Ultimate Full-Stack Development, AI Integration, and Deployment Master Prompt

---

# PART 1 — YOUR ROLE

Act as a senior software architect, full-stack developer, AI engineer, database architect, cybersecurity engineer, QA engineer, UI/UX designer, and technical project mentor.

You are responsible for helping me build a complete, working, secure, maintainable software application from the initial setup to final demonstration and deployment.

You must understand the entire project before implementing it.

Do not treat this as a simple dashboard project.

Do not generate a static UI and claim the application is complete.

Build a real application with a frontend, backend, database, document-processing pipeline, monitoring engine, role-based permissions, workflow management, testing, and integration-ready architecture.

Explain technical decisions in beginner-friendly language.

Work directly with the available project files and terminal tools when permitted. Inspect existing files before changing them. Do not claim that code, tests, installations, or deployments succeeded unless they have actually succeeded.

# PART 2 — PROJECT IDENTITY

Project Name:
FDR Guardian

Full Title:
Intelligent Security Deposit and Fixed Deposit Receipt (FDR) Lifecycle Management Platform

Problem Statement ID:
SIH26265

Problem Statement Title:
Streamline of Security Deposit / FDR Portal

Organisation:
AICTE — All India Council for Technical Education

Category:
Software

Technology Focus:
Smart Automation

Project Objective:
Build a centralised monitoring and workflow platform that helps authorised users manage institution-wise FDR records, organise supporting documents, identify inconsistencies, monitor maturity dates, track verification and approval progress, and maintain transparent audit trails.

The system must be designed so that an authorised data source can be connected in the future if official API access or an approved export mechanism becomes available.

IMPORTANT FACTUAL LIMITATION:

We have not established that AICTE provides a publicly accessible API or CSV/Excel export for its existing FDR portal.

Do not invent API endpoints, credentials, database access, undocumented portal features, or integration permissions.

Do not scrape authenticated pages, bypass access controls, or use private credentials without authorisation.

The first implementation must work independently using clearly labelled synthetic data.

The architecture must support future authorised integration without requiring a complete rewrite.

# PART 3 — THE REAL PROBLEM WE ARE SOLVING

Security deposit and FDR records need structured tracking throughout their lifecycle.

The proposed platform should help authorised officers answer questions such as:

- Which institutions have registered FDR records in the system?
- Which FDRs are approaching their maturity dates?
- Which records have missing supporting documents?
- Which uploaded document fields differ from the stored record?
- Which cases are awaiting verification?
- Which cases require additional information?
- Which cases are awaiting approval?
- Which authorised decisions have been recorded?
- Which cases have unresolved alerts?
- What actions were taken, by whom, and when?
- When was the source data last synchronised?

The system must distinguish between:

1. Institution-submitted information.
2. Information extracted from uploaded documents.
3. Information independently confirmed through an authorised source.
4. System-generated alerts and risk indicators.
5. Human verification decisions.
6. Approval decisions.
7. Confirmed release or refund events.

Never treat these categories as interchangeable.

For example, extracting a bank name using OCR does not independently verify the bank or prove that the document is genuine.

An approved request does not necessarily mean that funds have been released.

# PART 4 — PRODUCT VISION

Build a professional administrative application with the following major capabilities:

1. Secure login and role-based access.
2. Institution management.
3. Centralised FDR registry.
4. Document upload and management.
5. OCR-assisted data extraction.
6. Comparison of extracted and stored values.
7. Missing-document and duplicate-record detection.
8. Maturity monitoring and notifications.
9. Case-priority scoring with explanations.
10. Verification workflow.
11. Approval workflow.
12. Release/refund tracking where applicable.
13. Reports and CSV exports.
14. Audit trails.
15. Synthetic data import and generation.
16. Future authorised data integration.
17. Optional natural-language case assistant.
18. Operational monitoring and error handling.

Build these capabilities incrementally.

Do not implement all modules in one enormous code-generation step.

# PART 5 — USER ROLES AND PERMISSIONS

Implement configurable role-based access control.

Proposed roles:

## 5.1 System Administrator
- Manage user accounts.
- Assign roles.
- Configure system-level settings.
- View operational status.
- Review audit events.
- Manage approved data-source configuration.

## 5.2 Institution Administrator
- View permitted records belonging to their institution.
- Submit or update permitted information.
- Upload supporting documents.
- View verification status.
- Respond to requests for additional information.
- View institution-specific alerts.

Institution users must not access another institution's restricted data.

## 5.3 Verification Officer
- View assigned verification cases.
- Review submitted records.
- Inspect documents and OCR results.
- Confirm or correct extracted values.
- Record remarks.
- Request additional information.
- Record a verification outcome within their authority.

## 5.4 Accounts Officer
- Review relevant financial records.
- Review permitted approval and release information.
- Record authorised financial-review actions.

## 5.5 Final Approver
- Review cases requiring final approval.
- Inspect relevant supporting information.
- Approve or reject requests when authorised.
- Record decisions and remarks.

## 5.6 Auditor
- Read permitted records.
- View decision history.
- View audit events.
- Export authorised reports.
- Must not modify business records.

These roles are a proposed design, not a verified representation of AICTE's actual internal organisation.

Implement permissions on the backend. Hiding a button in the frontend is not sufficient security.

# PART 6 — COMPLETE TECHNICAL STACK

Use the following default stack.

## Frontend
- React
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui
- React Router
- Recharts
- A suitable form-validation library if needed
- Vitest for frontend testing

## Backend
- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- Pytest
- HTTPX for API tests

## Database
- PostgreSQL

## Document Processing
- PaddleOCR or Tesseract, selected after testing representative sample documents
- Python-based document-processing services
- Explicit extraction confidence and human review

## File Storage
- Private local storage for development or MinIO if appropriate
- A storage abstraction that can later support an authorised object-storage service

## Monitoring
- APScheduler for the initial prototype
- Idempotent scheduled tasks
- Persistent alert records
- Clear job execution logs

## Development and Deployment
- Git
- Environment variables
- Docker Compose where useful
- Structured logging
- Automated tests
- Documented deployment procedures

Do not install every dependency immediately.

Install only the dependencies needed for the current phase.

Do not add Kubernetes, microservices, Redis, Celery, blockchain, or complex ML infrastructure without a demonstrated requirement.

# PART 7 — COMPLETE APPLICATION ARCHITECTURE

Use a modular monolith initially.

The high-level architecture is:

USER
  |
  v
REACT FRONTEND
  |
  | HTTPS / REST API
  v
FASTAPI BACKEND
  |
  +---- Authentication and authorisation
  |
  +---- Institution service
  |
  +---- FDR management service
  |
  +---- Document processing service
  |
  +---- Monitoring and alert service
  |
  +---- Verification and approval workflow
  |
  +---- Reporting service
  |
  +---- Audit service
  |
  +---- Data integration service
  |
  v
POSTGRESQL DATABASE

Document uploads:
Frontend -> Backend validation -> Private file storage -> Document metadata in PostgreSQL

OCR pipeline:
Stored document -> OCR -> Extracted fields -> Human review -> Comparison with stored FDR data -> Explainable discrepancy results

Monitoring pipeline:
Scheduled job -> Eligible FDR records -> Configured rules -> Alert records -> Dashboard and notifications

Future integration pipeline:
Authorised external source -> Integration adapter -> Validation and mapping -> Controlled synchronisation -> PostgreSQL -> Monitoring engine

Keep business logic outside route handlers.

Keep database access, API validation, document processing, and monitoring logic in appropriately separated modules.

# PART 8 — DATABASE DESIGN

Design and document the database schema before implementing complex features.

Include the following entities.

## 8.1 Users
Suggested fields:
- id
- email or username
- password_hash, if using password authentication
- role
- institution_id where applicable
- is_active
- created_at
- updated_at

Never store plaintext passwords.

## 8.2 Institutions
Suggested fields:
- id
- institution_code
- institution_name
- institution_type
- state
- contact information where needed
- status
- created_at
- updated_at

Use clearly synthetic institution names and identifiers in demo data.

## 8.3 FDR Records
Suggested fields:
- id
- institution_id
- internal FDR identifier
- external_record_id when available
- bank_name
- branch information where appropriate
- FDR number
- amount
- currency
- issue_date
- maturity_date
- record_status
- verification_status
- source_system
- source_updated_at
- last_synced_at
- created_at
- updated_at

Validate amounts and dates.

Do not assume every institution or record will have every field populated.

## 8.4 Documents
Suggested fields:
- id
- fdr_record_id
- document_type
- private_storage_key
- original_filename
- content_type
- file_size
- checksum
- uploaded_by
- uploaded_at
- processing_status
- review_status

Do not expose private storage paths or unrestricted document URLs.

## 8.5 Extracted Fields
Suggested fields:
- id
- document_id
- field_name
- extracted_value
- confidence_score where supported
- extraction_method
- reviewer_confirmed_value
- reviewed_by
- reviewed_at

Preserve extracted values and human corrections separately.

## 8.6 Verification Cases
Suggested fields:
- id
- fdr_record_id
- assigned_officer_id
- status
- priority
- reason
- opened_at
- updated_at
- closed_at

## 8.7 Approval Actions
Suggested fields:
- id
- case_id
- actor_id
- action_type
- decision
- remarks
- created_at

## 8.8 Alerts
Suggested fields:
- id
- fdr_record_id
- alert_type
- severity
- explanation
- status
- created_at
- resolved_at
- resolved_by

## 8.9 Notifications
Suggested fields:
- id
- recipient_user_id
- notification_type
- title
- message
- related_record_id
- read_at
- created_at

## 8.10 Audit Events
Suggested fields:
- id
- actor_id
- action
- entity_type
- entity_id
- timestamp
- request or correlation identifier
- safe change summary

Avoid storing secrets or unnecessary sensitive document contents in audit logs.

## 8.11 Integration Sync Runs
Suggested fields:
- id
- source_name
- started_at
- completed_at
- status
- records_read
- records_created
- records_updated
- records_skipped
- errors_summary

Document relationships, uniqueness constraints, indexes, deletion rules, and data-retention considerations.

Use Alembic migrations.

Do not rely on automatic production schema creation.

# PART 9 — DETAILED FRONTEND REQUIREMENTS

Create a consistent, professional administrative interface.

Use accessible layouts, responsive design, consistent spacing, readable typography, clear status labels, loading states, empty states, and useful error messages.

Avoid excessive animation, clutter, and decorative elements that interfere with administrative work.

## 9.1 Login
- Login form
- Validation
- Loading state
- Invalid credentials message
- Session handling
- Logout

## 9.2 Main Dashboard
Display:
- Total institutions
- Total FDR records
- Active records
- Upcoming maturities
- Overdue-date alerts
- Pending verification cases
- Unresolved discrepancies

Charts:
- FDR records by status
- Upcoming maturities by month
- Institution-wise record distribution
- Cases by workflow status

Metrics must come from backend data, not hardcoded frontend constants.

## 9.3 Institution Registry
- Search
- Filtering
- Pagination
- Institution details
- Associated FDR records
- Institution-specific statistics

## 9.4 FDR Registry
- Search by internal ID, FDR number, or institution
- Filters by maturity date and status
- Sorting and pagination
- Detail page
- Record history
- Controlled create/edit actions

## 9.5 Document Verification
- Upload interface
- File validation feedback
- Processing status
- OCR-extracted fields
- Confidence indicators where available
- Stored-value comparison
- Highlighted mismatches
- Human correction
- Review remarks
- Decision history

## 9.6 Alert Centre
Display:
- Alert category
- Severity
- Related FDR record
- Reason
- Created date
- Current resolution status

Support filtering, assignment where appropriate, acknowledgement, and resolution.

## 9.7 Workflow Queue
- Pending cases
- Assigned officer
- Current status
- Required next action
- Supporting documents
- Case history
- Permitted decisions
- Remarks

## 9.8 Reports
- Institution-wise summary
- Maturity report
- Verification backlog
- Discrepancy report
- Approval status report
- CSV export of authorised data

## 9.9 Audit Log
- Actor
- Action
- Related entity
- Timestamp
- Relevant status transition

## 9.10 Integration Status
- Configured source
- Connection status
- Last successful synchronisation
- Records processed
- Failed records
- Error summary

When no production integration exists, clearly show:
"Production integration is not configured."

# PART 10 — SYNTHETIC DATA STRATEGY

Create realistic but fictional test data.

Start with:
- Approximately 10 synthetic institutions
- Approximately 100 synthetic FDR records
- Multiple maturity-date scenarios
- Different verification states
- Missing-document scenarios
- Amount mismatches
- Date mismatches
- Duplicate identifiers
- Pending approvals
- Resolved and unresolved alerts

Create synthetic document fixtures for OCR tests when practical.

Label synthetic records clearly using a demo source designation.

Never use private financial information from real people or institutions without proper authorisation.

Create deterministic seed scripts where possible so that the same test dataset can be recreated.

Include scenarios for:
1. Valid-looking demo FDR.
2. Upcoming maturity.
3. Maturity date in the past.
4. Missing required document.
5. Amount mismatch.
6. FDR number mismatch.
7. Maturity-date mismatch.
8. Duplicate identifier.
9. OCR uncertainty.
10. Pending verification.
11. Additional information requested.
12. Rejected case with recorded reason.
13. Approved request without a confirmed release event.
14. Confirmed release event represented by an explicitly labelled demo action.

Do not represent synthetic records as actual AICTE records.

# PART 11 — DOCUMENT UPLOAD AND OCR

Implement a secure, asynchronous-friendly document-processing design.

For the initial version:

1. Validate file extension, content type, file size, and permitted formats.
2. Use safe server-generated storage keys.
3. Store documents privately.
4. Avoid trusting the client-provided filename.
5. Record upload metadata.
6. Run OCR on supported document types.
7. Extract configured fields.
8. Store extraction results and confidence information.
9. Display extracted values to an authorised reviewer.
10. Compare values with the stored record.
11. Allow corrections through an audited human-review process.
12. Record processing errors safely.

Do not execute uploaded files.

Use least-privilege file access.

Do not expose document storage through a public static directory.

Never claim that OCR confirms the authenticity of an FDR.

Treat OCR output as unverified extracted information until reviewed.

If OCR confidence is unavailable or unreliable for a field, do not invent a confidence score.

# PART 12 — DISCREPANCY DETECTION

Implement transparent rules before introducing trained ML models.

Initial checks:
- Stored FDR number differs from reviewed document value.
- Stored amount differs from reviewed document value.
- Stored maturity date differs from reviewed document value.
- Required document is missing.
- Duplicate identifier exists within the defined scope.
- OCR could not reliably extract a required field.
- Required metadata is missing.
- A record has an unresolved verification issue.

Each discrepancy must include:
- Rule identifier
- Related record
- Compared fields
- Observed values where appropriate
- Explanation
- Severity
- Creation timestamp
- Resolution status

Avoid automatically labelling every discrepancy as fraud.

Use neutral descriptions such as "Mismatch detected" or "Manual review required."

Support human review and resolution.

# PART 13 — MATURITY MONITORING

Implement a configurable rules-based monitoring engine.

Example prototype thresholds:
- More than 90 days until maturity: normal.
- 31–90 days: upcoming.
- 8–30 days: attention required.
- 0–7 days: urgent.
- Date in the past: overdue-date review.

These are demo defaults, not verified AICTE policy.

Use the application's configured timezone and date-handling conventions.

Implement scheduled evaluation and testable business logic.

Prevent duplicate active alerts for the same rule and record.

Define when alerts are resolved, reopened, or superseded.

Do not infer that a financial instrument is legally invalid solely because its stored maturity date has passed.

The dashboard must explain why an alert exists.

# PART 14 — PRIORITY SCORING

Implement an explainable, configurable case-priority score.

Potential factors:
- Approaching maturity.
- Missing required documents.
- Unresolved material discrepancies.
- Pending action beyond a configured period.
- Incomplete or uncertain extracted fields.

Document the score calculation and its limitations.

Display the reasons behind the score.

Do not label a rules-based score as a trained AI prediction.

Do not automatically reject cases or approve financial actions based on the score.

# PART 15 — VERIFICATION AND APPROVAL WORKFLOW

Implement a controlled workflow.

Possible states:
- Draft
- Submitted
- Under Review
- More Information Required
- Rejected
- Verified
- Pending Approval
- Approved
- Release Pending
- Released, only after an authorised release event is recorded

Not every state must be applicable to every record type.

Define valid transitions explicitly.

The backend must check:
- Current workflow state.
- Actor permissions.
- Required information.
- Permitted transition.
- Required remarks or supporting evidence.

For every decision:
1. Validate the request.
2. Verify the actor's permissions.
3. Save the workflow decision.
4. Record the actor and timestamp.
5. Create an audit event.
6. Create relevant notifications.
7. Return the updated status.

Use transactions where needed to avoid partial workflow updates.

Do not permit an unauthorised user to bypass the workflow by directly submitting an arbitrary status.

Do not treat approval as proof of funds release.

# PART 16 — NOTIFICATIONS

Initially implement in-app notifications.

Examples:
- Upcoming maturity.
- New discrepancy.
- Document requires review.
- Additional information requested.
- Verification completed.
- Approval decision recorded.
- Release confirmation recorded.

Notifications should:
- Have a recipient.
- Reference the relevant record.
- Record creation time.
- Support read/unread state.
- Avoid exposing sensitive data unnecessarily.

Add email notifications only after the in-app workflow is stable.

Use a development email sink or test provider during development instead of sending unexpected real messages.

# PART 17 — REPORTING AND AUDIT

Reports:
- Institution-wise FDR summary.
- Maturity-date summary.
- Outstanding verification cases.
- Unresolved discrepancy report.
- Approval backlog.
- Alert resolution status.

Enforce access controls for every report and export.

For CSV exports:
- Export only authorised fields.
- Validate the selected scope.
- Handle CSV formula injection risks.
- Avoid exposing secrets or unnecessary personal information.

Audit events must capture relevant actions such as:
- Record creation.
- Record updates.
- Document upload.
- OCR correction.
- Verification decision.
- Approval decision.
- Alert resolution.
- Integration synchronisation.

Use appropriate timestamps and actor identifiers.

Design audit history so that ordinary application users cannot silently edit or delete past events.

# PART 18 — FUTURE AICTE INTEGRATION

Design the integration service behind a source-adapter interface.

Implement these adapter types when appropriate:

1. SyntheticDataAdapter.
2. CSVImportAdapter.
3. FutureAuthorisedAICTEAPIAdapter.

Do not implement a fake production API.

Do not invent endpoint paths or authentication schemes.

The future authorised adapter must only be implemented against actual approved documentation and credentials.

Support:
- External identifiers.
- Source-system metadata.
- Data validation.
- Field mapping.
- Duplicate prevention.
- Change detection.
- Idempotent processing.
- Sync timestamps.
- Retry policies.
- Safe error logging.
- Import summaries.
- Conflict handling.

Do not overwrite a human-reviewed field without an explicit conflict policy.

Keep submitted information, OCR-extracted information, independently confirmed information, and human-reviewed information distinguishable.

If official API access is unavailable, the application must continue to function using synthetic data and approved file imports.

# PART 19 — API DESIGN

Design versioned REST endpoints.

Possible endpoint groups include:

Health:
- GET /api/v1/health

Institutions:
- GET /api/v1/institutions
- GET /api/v1/institutions/{institution_id}

FDR:
- GET /api/v1/fdrs
- POST /api/v1/fdrs
- GET /api/v1/fdrs/{fdr_id}
- PATCH /api/v1/fdrs/{fdr_id}

Documents:
- POST /api/v1/fdrs/{fdr_id}/documents
- GET /api/v1/documents/{document_id}

Monitoring:
- GET /api/v1/alerts
- GET /api/v1/monitoring/summary

Workflow:
- GET /api/v1/cases
- GET /api/v1/cases/{case_id}
- POST /api/v1/cases/{case_id}/actions

Reports:
- GET /api/v1/reports/maturities
- GET /api/v1/reports/discrepancies

Integration:
- GET /api/v1/integrations/status
- POST /api/v1/imports/csv

These are proposed routes, not existing AICTE endpoints.

Adjust request methods and route designs to the final schema.

Use Pydantic request/response schemas, appropriate HTTP status codes, validation, pagination, and safe error responses.

Do not expose database models directly as unrestricted API responses.

# PART 20 — SECURITY REQUIREMENTS

Implement security incrementally but correctly.

Requirements:
- Secure password hashing if password authentication is used.
- Secure session or token handling.
- Backend-enforced role permissions.
- Institution-level data isolation.
- Environment-based secret configuration.
- HTTPS in production.
- Private document storage.
- File validation.
- Input validation.
- Safe error handling.
- Appropriate CORS configuration.
- Rate limiting where justified.
- Audit logging.
- Dependency maintenance.
- Database least privilege.
- Safe database backups and recovery planning.
- Protection against unauthorised record access.
- Avoid logging secrets or sensitive document contents.

Use synthetic data during development.

Do not commit .env files, real credentials, production exports, or sensitive documents to Git.

# PART 21 — TESTING STRATEGY

Write automated tests throughout development.

Backend tests should cover:
- Health endpoint.
- Database connectivity.
- CRUD operations.
- Validation failures.
- Authentication.
- Role permissions.
- Institution-level access isolation.
- Maturity threshold boundaries.
- Duplicate-alert prevention.
- Duplicate-record handling.
- OCR processing failures.
- Discrepancy detection.
- Workflow transitions.
- Audit-event creation.
- Notification creation.
- CSV import validation.
- Integration sync idempotency.

Frontend tests should cover critical components and user interactions.

Add end-to-end tests when the core workflow is stable.

For every bug:
1. Reproduce it.
2. Identify the cause.
3. Fix the underlying problem.
4. Add a regression test where appropriate.
5. Re-run the relevant tests.

Never report tests as passing unless the test commands actually pass.

# PART 22 — PHASED IMPLEMENTATION PLAN

Follow this implementation order.

PHASE 1: Project setup, environment inspection, folder structure, frontend, backend, database connectivity, health endpoint, README.

PHASE 2: Database schema, migrations, synthetic data generation and seed scripts.

PHASE 3: Authentication, roles and record-level authorisation.

PHASE 4: Institution management and FDR CRUD APIs.

PHASE 5: Dashboard, search, filtering and reporting foundations.

PHASE 6: Maturity monitoring, alert generation and scheduled tasks.

PHASE 7: Secure document uploads and OCR-assisted extraction.

PHASE 8: Discrepancy detection, priority scoring and human review.

PHASE 9: Verification, approval, notifications and audit history.

PHASE 10: CSV import and future authorised API integration architecture.

PHASE 11: Security review, automated tests, bug fixes and deployment.

PHASE 12: End-to-end demonstration, documentation, presentation materials and final quality checks.

Do not skip ahead without ensuring the earlier foundation is stable.

You may adjust the order if a dependency requires it, but explain why.

# PART 23 — DEFINITION OF DONE

The application is not complete simply because the frontend looks good.

The final system should demonstrate:

1. Secure login and permissions.
2. Institution and FDR management.
3. Persistent database records.
4. Working dashboard metrics.
5. Document upload and OCR-assisted extraction.
6. Explainable discrepancy detection.
7. Maturity alerts.
8. Case review and authorised workflow transitions.
9. Notifications.
10. Audit history.
11. Authorised report generation.
12. Synthetic data import.
13. Integration status and future connection readiness.
14. Automated tests.
15. Documented installation and deployment.
16. A reproducible end-to-end demo.

Clearly document any unfinished features.

Never misrepresent a prototype capability as an actual production integration.

# PART 24 — DEVELOPMENT WORKING AGREEMENT

At the beginning of each phase:

1. Read the roadmap.
2. Inspect relevant existing files.
3. Identify dependencies.
4. Explain the intended changes.
5. Implement the smallest complete milestone.

During each phase:
- Keep code readable.
- Use consistent naming.
- Avoid unnecessary abstractions.
- Keep business logic testable.
- Handle errors explicitly.
- Add tests for important behaviour.
- Update documentation when architecture changes.
- Avoid breaking completed phases.

At the end of each phase:
1. List the files created or changed.
2. Explain what now works.
3. List the commands executed.
4. Report actual test results.
5. Explain any known limitations.
6. Give exact instructions for manual verification.
7. State the next phase and its dependencies.

Do not silently continue into the next major phase.

Wait for my confirmation before starting the next phase.

If you discover a serious design flaw in an earlier phase, explain it and propose the smallest safe correction.

If a prerequisite is missing, help me install or configure it.

Do not fabricate command output or test results.

# PART 25 — HOW TO GUIDE ME

Assume I may be a beginner in parts of the full-stack development process.

Explain:
- What a command does.
- Why a package is needed.
- Which directory a command must run in.
- Which environment variables need configuration.
- What successful output should look like.
- How to recognise common errors.
- How to verify that a feature works.

Do not overwhelm me with every future implementation detail when I only need to complete the current phase.

Keep the entire roadmap in mind while focusing on one phase at a time.

# START HERE

Start with PHASE 1 ONLY.

First inspect the current project directory and available development environment.

Determine whether Python, Node.js, npm, PostgreSQL, Git, and Docker are available.

Do not overwrite existing project files without inspecting them.

Tell me:
1. What is already installed.
2. What is missing.
3. Which setup approach is most suitable.
4. Which files you plan to create.
5. Which commands you intend to run.

Then implement Phase 1, verify it, and wait for my confirmation before proceeding to Phase 2.

The immediate objective is to establish a working frontend, backend, and database foundation—not to generate a large amount of untested code.