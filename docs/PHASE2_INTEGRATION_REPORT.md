# AVSAR Phase 2 integration and remediation report

## Integration baseline and history

Working branch: codex/avsar-phase2-integration. Isolated worktree: ABSAR-integration (sibling of the original backend workspace). Base: published backend 32777e8d91d0aab22ba7761bae9f69fc203e59ae.
Published AI branch integrated: 77d9c9150477f369bfd12e18c996e0f64fb47288.
Published frontend integrated: 5444c9822f7f9ce194343fbde7b6eb80b3a92fe5.

Merge commits created:
- 5d0f69f: Integrate published AI services while retaining backend compatibility entry points.
- 5155023: Integrate published frontend and provider-aware authentication.

The AI merge had conflicts in resume_analyzer, trust_checker and scraper, plus tests relocated by the backend layout. Member 1 implementations were retained, backend-only compatibility behavior was separated into adapters, and both test sets were preserved. The frontend merge was clean. Published feature branches and main were not rewritten or merged into. Original backend uncommitted files were not copied wholesale into this worktree or discarded. The targeted eligibility correction was applied only in this integration worktree and receives regression coverage.

## Canonical shared contracts

See INTEGRATION_CONTRACTS.md, regenerated API_CONTRACTS.json, openapi.json and ENDPOINT_INVENTORY.md. Reconciliation uses the published service signatures, frontend constants/client and backend schema authority. This is implementation-level coordination; it does not assert separate human sign-off from the other members.

- All 11 categories and three modes agree across extraction/backend/frontend; contract tests compare them.
- Profiles preserve demographic fields and owner-controlled optional inputs. Confirmed typed demographic rules are deterministic; no category implies an invented rule.
- Recommendation and eligibility APIs use one engine decision. Unconfirmed means unknown. Explicit confirmed empty criteria means reviewed unrestricted.
- Resume adapter consumes Member 1 analyze_resume(text_or_pdf, opportunity=None), preserves all computed fields, adds backend ownership, warnings and backward-compatible claims/evidence. It does not replace the deterministic analyzer.
- Trust result contains independent backend risk fields plus Member 1 source_assessment. Scores are not inverted. Official-domain matching is not proof of legitimacy. GET retrieval does not create analysis.
- Data/meta success envelope and detailed errors retained; single results and paged lists are handled explicitly by the frontend.
- Ten backend application states remain authoritative with explicit review/approve/confirm/idempotent-submit actions. Submission receipt is user reported, not verified portal delivery.

## Nine defects remediated

| Defect | Correction | Evidence |
|---|---|---|
| Matcher/adapter disagreed | Matching uses deterministic adapter result; confirmation policy unified | Four cross-API decision cases plus real HTTP comparison |
| Duplicate ingest lost later facts | Distinct append-only observations retain source data, metadata and conflicts; canonical identity remains stable | Two source observations retained, repeated observation idempotent |
| Exhausted crash recovery left PROCESSING | Recovery transitions notices to RETRY/FAILED and clears lease; completed states protected | Expired third-attempt job becomes DEAD_LETTER and notice FAILED |
| Refresh limited forever to first 100 | Stable record paging/cursor iteration, with allegation filtering | Eligible record behind 105 allegations is refreshed |
| Denials became suspicious | Signal-specific negation handling shared by risk and Member 1 checker, preserving affirmative clauses | Denied OTP/guarantees and mixed positive request cases; Member 1 suite retained |
| Trust GET wrote reports | Missing analysis is 404; explicit POST creates snapshot/report; frontend button calls POST | Row counts unchanged by GET; POST then GET succeeds |
| Resume signature mismatch | Inspect supported callable shape, consume rich result and validate ownership; retain original analyzer | Real rich analyzer + resume worker/API regressions |
| Fuzzy dedupe unused | Catalog invokes Member 1 exact/fuzzy comparison, stores review decisions and observations, never auto-merges | Similar entries stay separate with HUMAN_REVIEW_REQUIRED record |
| Category/profile mismatch | Exact 11-category schemas/AI/frontend checks; demographic requirement mapping and preserving UI fields | All-category cross-contract tests, income/domicile known/missing cases |

## Integration details

Registered Member 1 source adapters are operator-enabled through DISCOVERY_SOURCES, use pinned safe-fetch transport, preserve source attribution/retrieval/raw provenance, and enter the same ingestion path. RSS compatibility remains. Invalid source IDs and arbitrary URL overrides are not allowed. Source HTML transport is mocked in the registered-source regression; live external website parsing is not claimed.

The frontend retains its published theme and Next 14/React 18 stack. Changes are functional: optional profile facts, rich resume result rendering, distinct trust signals, and separate application preparation/material review/approval/confirmation with stable idempotency keys. Existing provider-aware token precedence and Supabase refresh behavior are retained. Post-submission tracking still uses allowed status transitions.

## Test results and failures encountered

Initial integration baseline: `python -B -m pytest app/tests -q -p no:cacheprovider` -> 214 passed, 2 failed, 1 skipped. Both failures were resume worker/result incompatibility. After adapter fixes, one old trust test still expected GET to create analysis; it was updated to create explicitly with POST and new tests prove GET has no writes. No failing test was skipped or disabled.

Final complete configured backend suite: `python -B -m pytest -q -p no:cacheprovider` -> **283 passed, 0 failed, 1 skipped**, 13 third-party deprecation warnings, 43.99 seconds. Pytest configuration now includes published Member 1 resume/scraper/trust test files in addition to app/tests. The unchanged optional deployment test skips because unrelated render.yaml is not part of this branch; this is not a suppressed application failure.

New targeted tests: app/tests/test_phase2.py (28 cases), app/tests/test_eligibility_groups.py (8 cases). Existing Member 1 and backend tests remain. Individual suites overlap; no inflated independent totals are claimed.

Frontend: `npm ci --no-audit --no-fund` installed the published lock without dependency updates; `npm test` -> **11 passed, 0 failed**; `npm run lint` passes with one existing custom-font warning; `npm run build` compiles and generates 12 pages. Tests cover provider token precedence/expiry/refresh, submission request/idempotency shape, canonical categories, registered submit/result contracts and trust display semantics.

Security/code checks:
- `ruff check main.py app migrations scripts` -> passed.
- `ruff format --check main.py app migrations scripts` -> passed.
- `bandit -q -r main.py app -x app/tests` -> passed; existing narrow bearer-literal nosec warnings.
- `python scripts/validate_dependencies.py` -> 122 pins validated. requests was made a direct requirement; its existing compatible locked version was retained.
- `pip check` -> no broken requirements.
- `pip-audit -r requirements.lock.txt --no-deps --disable-pip` -> no known vulnerabilities reported for backend core lock.
- `python scripts/export_stage1_contracts.py --check` -> passed.
- `git diff --check` -> passed.

## Live local runtime evidence

`python scripts/smoke_phase2.py` uses a private temporary SQLite database, Alembic upgrade and schema comparison, actual Uvicorn HTTP transport and actual deterministic services. Passed startup/readiness/CORS, local signup, unauthorized profile rejection, profile/catalog, matching/eligibility agreement, trust GET/POST, application review/approval/confirmed submit and identical receipt on retry, calendar and resume upload/job/result. No live AI provider was used or mocked in this smoke: resume/trust are actual deterministic implementations.

The first smoke completed workflows but failed Windows temp-file cleanup after terminating its subprocess launcher. The smoke helper was fixed to shut Uvicorn down gracefully in-process and dispose connections. Final smoke exited 0 including cleanup. No existing application server or database was modified.

Production frontend was started on an isolated localhost port; /login, /opportunities, /applications, /resume and /profile returned 200. It was then stopped. This proves production HTTP startup/routing, not browser hydration or user click-through.

The agent-browser skill was inspected, but its CLI/runtime is not installed. Full browser E2E and responsive visual QA are not claimed. Actual Supabase, Gemini, Postgres/Mongo and Redis/Celery transport require staging credentials/services; local tests use SQLite/eager jobs and mocked external signatures/transports where stated.

## Security release blocker: published frontend dependencies

`npm audit --omit=dev --json` exits 1 with **2 affected package findings: 1 critical (next), 1 high (its bundled postcss)**. Multiple advisories contribute to those package severities. npm offers a semver-major Next 16.4.6 migration, not a routine update inside the published Next 14 scope. The framework was not silently upgraded across Member 3 ownership.

Examples: https://github.com/advisories/GHSA-h25m-26qc-wcjf and https://github.com/advisories/GHSA-r28c-9q8g-f849. Actual exploitability of every advisory was not established. The locked dependency finding remains a release blocker even though build and functional checks pass. Coordinate a supported security migration with Member 3 and repeat compatibility/build/auth/E2E checks before release. No npm audit fix --force was run.

## Remaining blockers and limits

P1: frontend dependency security findings above. This branch is a working integration baseline, not production-ready.
P2: real Supabase/Gemini/registered-source sites and hosted database/broker crash-recovery/RLS/checkpoint grants still need staging verification.
P2: full browser E2E and human review of new demographic/source/lifecycle contracts remain outstanding.
P2: duplicate candidate scan and recommendation/calendar windows retain bounded 500-record coverage; no automatic merge or infinite full-catalog assumption.
P3: regex-based negation and resume completeness estimates remain heuristics, with limitations shown. No trust or qualification certainty is claimed. Existing custom-font lint warning remains.

## Commit/publication scope

Only the dedicated integration branch is authorized for publication. Remediation commit subject: `Fix integrated ingestion, eligibility, resume and approval workflows`. Exact resulting commit hash and remote hash verification are supplied in the final handoff because a commit cannot contain its own hash. No main merge, feature-branch overwrite, force push or history rewrite is performed. The original backend worktree remains on backend-code with its excluded local changes preserved.

## Remediation file inventory

- `README.md`
- `backend/app/config/settings.py`
- `backend/app/integrations/member1.py`
- `backend/app/integrations/negation.py`
- `backend/app/integrations/resume_claims.py`
- `backend/app/integrations/risk_compat.py`
- `backend/app/integrations/rss_ingestion.py`
- `backend/app/models/resume.py`
- `backend/app/models/trust_report.py`
- `backend/app/repositories/documents.py`
- `backend/app/routes/discovery.py`
- `backend/app/routes/opportunities.py`
- `backend/app/routes/trust.py`
- `backend/app/schemas/opportunity.py`
- `backend/app/services/catalog.py`
- `backend/app/services/eligibility_adapter.py`
- `backend/app/services/eligibility_engine.py`
- `backend/app/services/jobs.py`
- `backend/app/services/matching.py`
- `backend/app/services/resume_analyzer.py`
- `backend/app/services/scraper.py`
- `backend/app/services/trust_checker.py`
- `backend/app/services/verification_refresh.py`
- `backend/app/tests/test_eligibility_groups.py`
- `backend/app/tests/test_layout.py`
- `backend/app/tests/test_phase2.py`
- `backend/pyproject.toml`
- `backend/requirements.txt`
- `backend/scripts/export_stage1_contracts.py`
- `backend/scripts/smoke_phase2.py`
- `backend/tests/test_trust.py`
- `docs/API_CONTRACTS.json`
- `docs/ENDPOINT_INVENTORY.md`
- `docs/INTEGRATION_CONTRACTS.md`
- `docs/PHASE2_INTEGRATION_REPORT.md`
- `docs/TEAM_RESPONSIBILITIES.md`
- `docs/openapi.json`
- `frontend/src/app/applications/page.js`
- `frontend/src/app/opportunities/[id]/page.js`
- `frontend/src/app/profile/page.js`
- `frontend/src/app/resume/page.js`
- `frontend/src/components/TrustBadge.js`
- `frontend/src/services/api.js`
- `frontend/src/services/application-contract.mjs`
- `frontend/src/services/trust-state.mjs`
- `frontend/tests/application-contract.test.mjs`
- `frontend/tests/contract-alignment.test.mjs`
- `frontend/tests/trust-state.test.mjs`
