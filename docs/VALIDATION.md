# Verification record

Executed locally for this rebuild across 14Ã¢â‚¬â€œ15 November 2026. Results describe this workspace and mocked/offline behavior, not a live cloud deployment.

| Check | Recorded result |
| --- | --- |
| Full backend pytest suite | **122 passed**, 13 third-party LangSmith deprecation warnings; Python 3.14.10 on Windows |
| Ruff lint | Passed for app, tests, migrations and scripts |
| Ruff formatting | 96 files passed the final format check |
| Bandit | Passed; two narrow B105 exclusions cover the OAuth literal `token_type="bearer"`, not credentials |
| pip-audit | No known vulnerabilities after upgrading Pillow to 13.0.0 |
| Dependency manifest validation | Passed, 122 pinned entries including the conditional Linux uvloop pin |
| Alembic upgrade | Applied successfully to local SQLite |
| Alembic schema comparison | No new upgrade operations detected |
| Operator indexes command | Completed locally; Atlas creation still requires a configured hosted connection |
| Operator checkpoint command | Created/checked SQLite checkpoint structures successfully |
| Python compileall | Passed for app and migrations |
| Frontend clean install | Final `npm ci --ignore-scripts --no-audit --no-fund` completed successfully |
| Frontend lint after clean install | Passed without warnings under Node 22.23.5 |
| Frontend production build | Passed on Node 26 and on the specified Node 22 runtime; 11 generated pages plus the dynamic opportunity-detail route |
| Frontend dependency audit | Zero reported vulnerabilities after the scoped lint-parser minimatch override |
| Git whitespace check | Passed |

The suite covers real locally generated Supabase/Cognito asymmetric signatures and invalid claims, hosted configuration rejection, owner isolation, deterministic matching/coverage and general eligibility utilities, fee negation and expiry, private history, DNS/redirect SSRF defenses, stable duplicate insertion, PDF/DOCX/OCR bounds, notice review, resume claims, immutable application approval/submission, retry semantics, leased jobs and outbox failures, assessments/hidden answers, optional mocked Judge0, career checkpoints and controls, mocked RSS/Gemini/Resend, telemetry redaction, and deployment/manifest rules. Former placeholder smoke tests were replaced with real service assertions.

The Windows sandbox prevented asyncio from creating its local event-loop socket pair. API tests were therefore executed with approved local socket access. Cloud services remained deterministic or mocked and did not require cloud credentials.

Python dependencies were resolved in a clean workspace virtual environment. Pillow's initial audit findings were fixed and rechecked. The original Next.js 14 tree had high/critical advisories; the build setup was updated to Next.js 16.4.6/React 19.3.1 and validated. The remaining lint-only minimatch advisory was resolved through a narrowly scoped override and verified with the package audit.

Docker is not installed on this host. Docker image startup, Compose execution, actual Python 3.12 execution, GitHub-hosted workflows and live cloud deployments have **not** been run here. CI defines Python 3.12/3.14 and Node 22 checks. Actual PostgreSQL RLS/advisory locks, Atlas indexes, broker process-failure recovery, OAuth/key rotation, external mail delivery, model-account access and independently isolated Judge0 require the staging integration checks in OPERATIONS.md.


## Chart-based layout verification â€” 15 November 2026

Moved all regression tests into `backend/app/tests`, domain definitions into the named model/schema files, real handlers into `app/routes`, JWT verification into `utils/auth.py`, and bounded upload handling into `utils/file_handler.py`. `backend/main.py` is the public entry point. Replaced the requested scraper/resume/trust placeholders with functional services and retained required worker/migration support.

The complete relocated suite passed **121 tests**. New checks cover every chart source path, entry-point identity, profile/catalog/feed routes, separate four-status eligibility responses, batch limits, private resume matching, conservative trust output and calendar owner isolation. Ruff lint/format, Bandit (excluding tests), dependency consistency and Alembic drift checks passed after the refactor. API exports contain **19 payload schemas and 80 OpenAPI paths**. Docker startup remains untested because Docker is unavailable here. Frontend build/audit results above are from the earlier verified integration setup; the layout refactor did not require a frontend build change.


## CI discovery fix — 15 November 2026

The screenshot failure came from the old workflow command `python -m unittest discover -s backend/tests` after tests had moved to `backend/app/tests`. The backend commit had been pushed without the updated workflow. The complete project integration now runs `python -m pytest app/tests -q` from the backend directory, tests Python 3.12 and 3.14, and includes backend-code in push triggers. A regression check covers this workflow/path contract. The corrected command passed all **122 tests** locally; actual GitHub checks are evaluated separately after pushing.
