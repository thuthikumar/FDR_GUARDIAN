# Project instructions

## Project specification and phase boundaries

- `docs/MASTER_PROMPT.md` is the project specification. Follow its phase order.
- Work on one phase at a time. Never start the next phase without the user's confirmation.
- Never claim access to AICTE production data, APIs, or real FDR records. Clearly label all development data as synthetic.
- Inspect files before changing them. Install only dependencies needed for the current phase.
- Use Alembic for database migrations. Enforce permissions on the backend; frontend-only checks are not security controls.
- Never claim a test or command passed unless it was actually run. Report the real result.
- In Windows PowerShell, use `npm.cmd` when `npm.ps1` is blocked by execution policy.
- At the end of every phase, report: files changed, commands run with actual results, how to verify manually, known issues, and the next phase.

## Git workflow

- Keep `main` working. The Phase 1 baseline may be committed on `main`; after that baseline, never commit directly to `main`.
- Use one branch per phase, named `phase-N-short-name` (for example, `phase-2-database-schema`).
- Make small commits with Conventional Commit prefixes: `feat:`, `fix:`, `test:`, `docs:`, `chore:`, or `refactor:`.
- Before every commit, run relevant tests, inspect `git status`, and confirm no `.env`, secrets, uploads, private documents, or generated data are staged.
- At the end of a phase, push its branch with `git push -u origin <branch>` and report the result. Do not merge it.
- The user will confirm before merging. Then merge into `main` with `--no-ff`, tag `phase-N-complete`, and push `main` and tags.
- Never force-push, rewrite history, or delete branches unless the user explicitly asks.
