# Capability and compatibility report

## Reference and implementation

The workspace repository's origin is `https://github.com/MAANDUBEY07/ABSAR.git`. The available checkout contained real `eligibility_engine.py`, `duplicate_detector.py`, `notice_parser.py`, and `ai_extractor.py` utilities and tests. Most API routes, models, persistence configuration and scraper/trust/resume service files were placeholders. No persistent OpportunityOS matching formulas, Strands orchestration or browser-submission implementation existed in this checkout. This rebuild does not claim byte-for-byte reproduction of a different unpublished backend.

The reusable eligibility engine retains its operators, weighted preferential/mandatory criteria, nested lookup, age derivation, diagnostics and external/internal status distinctions. The fuzzy duplicate detector remains available as a compatibility utility. The canonical persistent catalog uses a deterministic fingerprint, not an undocumented fuzzy merge policy. Existing utility tests remain, with formatting/import cleanup for CI.

## Implemented persistent behavior

- FastAPI `/api/v1`, safe envelopes/errors/request IDs, OpenAPI/docs and health/readiness.
- Supabase asymmetric JWT verification, configured Cognito ID-token compatibility, local development JWT/signup/login, owner predicates and signed notification email.
- Hosted configuration guards; SQLAlchemy owned records, explicit revisions/keys/foreign keys, Alembic migration, MongoDB collections/index command and durable local SQL document fallback.
- Editable student profile plus normalized skills/education/preferences; canonical public opportunity submissions and bounded configured RSS discovery.
- Deterministic eligibility/ranking with uncertainty and coverage; private heuristic risk evidence, allegations, history and source snapshots.
- Deferred resume and notice parsing, metadata/bytes persistence, PDF/DOCX/OCR boundaries, quoted skill claims and human notice confirmation. Persistent notice drafts are deterministic; the Gemini utility is separate.
- Immutable application versions/approvals/audits through application behavior, optimistic revisions, approval digest binding, material-change invalidation and scoped submission idempotency. Receipts are USER_REPORTED and externally unverified.
- Starter assessment bank, deterministic answers, immutable attempts, interview rubrics and fail-closed optional isolated Judge0 jobs.
- Owner-scoped LangGraph checkpoints, PostgreSQL advisory locking, learning suggestions (deterministic or configured Gemini/Bedrock), draft proposals, snapshot monitoring, milestones, pause/resume/cancel and checkpoint reuse.
- Durable SQL jobs/outbox, at-least-once Celery delivery, attempts/leases/fencing, cancellation, stale recovery, one beat scheduler, in-app reminders, opt-in Resend calls with provider idempotency keys.
- Docker/Compose, Render and Vercel setup, environment templates, dependency validation, normal CI, production build checks and optional manual AWS preflight.

## Honest limits and assumptions

| Area | Boundary |
| --- | --- |
| Legacy contract | `/api` adapters are development-only; hosted requests receive 503. Most old schemas/routes were placeholders, so exact historical response reproduction cannot be asserted. Shared adapters generally use v1 envelopes; dedicated legacy login, catalog, document and activity adapters use their documented simpler forms. Recovery/MFA fail closed through external auth requirements. |
| Authentication | Logout clears the client's session; issued access tokens remain usable until expiry. JWKS retrieval trusts only configured provider URLs. Real key rotation/OAuth requires integration tests. |
| Matching | Preference/experience/learning formulas are explicit assumptions because their persistent reference implementation was absent. A high ranking never overrides a failed mandatory criterion. |
| Risk | Fee, guaranteed-selection, sensitive-data and domain-difference heuristics are not a verified fraud classifier. A zero score means no implemented signals detected. Employer identity remains UNKNOWN unless a supplied deadline is expired. Reports are allegations. |
| Documents | Skills are lexical resume claims with a starter vocabulary; broad semantic skill/experience inference is not implemented. OCR quality depends on local Tesseract/languages. No extracted skill changes the profile automatically. |
| AI | Suggestions cannot mutate eligibility, verified facts, risk evidence, approval permissions or correctness. Model cost remains null. Persistent notice extraction does not automatically invoke the standalone Gemini extractor. |
| Applications | No browser/portal submission tool, credentials collection or unattended employer submission. Approval comes from the authenticated student and is bound to material, not from model text. |
| Career | Plans and draft proposals are bounded snapshots. Messages persist as notes and cannot grant permissions; they do not automatically trigger a model replan. This is not an always-running autonomous career monitor. Pause/resume can intentionally produce a new execution revision; completed checkpoints are reused within an execution. |
| Jobs | Three processing attempts; broker errors retain the SQL outbox. Cancellation cannot reverse an already-started external request. SQL/MongoDB are not a distributed transaction. External providers can observe retries. |
| Notifications | Reminder batches are bounded; there is no guarantee every large catalog/user population is covered by a single run. Resend acceptance does not prove delivery. Production-scale retention, paging/fair maintenance sweeps and account deletion/export remain operator work. |
| Judge0 | Optional infrastructure must be independently isolated, configured and tested. The API never evaluates arbitrary code locally. Starter execution quota is five jobs per owner, not a production billing/quota system. |
| AWS | Bedrock/Cognito adapters and a token-authenticated AgentCore boundary are optional. No DynamoDB/S3/Strands/CloudWatch deployment is fabricated where the reference only had placeholders or absent files. |
| Frontend | Existing screens/services remain largely placeholders. Build/deployment settings do not make them a complete working Supabase/v1 student UI. |
| Deployment | Config files and offline tests do not establish a live deployment or validate real provider accounts. Docker runtime and hosted infrastructure require separate verification. |

The chart-based reorganization replaces the former route/service placeholders with registered implementations. The real RSS connector is in `scraper.py`, lexical resume claims in `resume_analyzer.py`, and deterministic risk rules in `trust_checker.py`. The root `backend/main.py` exports the assembled app; tests live under `app/tests`. Calendar endpoints derive owner-scoped application deadlines and do not claim external synchronization. MongoDB collection extension points are not evidence of workflow activity until real events are written.

## Required hosted integration verification

Before production sign-off, test actual PostgreSQL row/advisory locking, RLS/runtime permissions, Atlas unique indexes and outage handling, Redis/Celery delivery/recovery under process termination, Supabase OAuth/JWKS rotation, Resend provider idempotency/delivery, real isolated Judge0 behavior, Gemini/Bedrock model access and structured output, OCR in the container, Docker image startup and Render/Vercel deployment. Ordinary tests use SQLite, deterministic providers and mocks; they cannot prove these hosted behaviors.
