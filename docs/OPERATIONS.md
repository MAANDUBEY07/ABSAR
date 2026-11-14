# Setup and operations

## Account connections and secrets

Create a Supabase project, Atlas database/user, Redis service, Gemini API credentials and a Render account. Add a Vercel project pointing to this repository. None of these resources are provisioned by the source files.

Copy `backend/.env.render.example` values into an external Render environment group named **opportunityos-backend**. Replace every placeholder. All three Render services import that group and the same explicit hosted safety settings. Use TLS database/broker connections, narrowly scoped database users and Atlas network rules. The direct PostgreSQL connection must support migrations and advisory locks; run migrations with a separate schema-owner credential. The application runtime should use a separate non-owner role with no DDL or schema ownership. Supabase transaction pooling must be evaluated carefully for session-sensitive tooling/checkpoint connections; a direct or suitable session-pool connection is recommended for operator setup. Back up SQL, MongoDB and checkpoints before upgrades.

`AUTH_PROVIDER=supabase`, `AWS_ENABLED=false`, `AI_PROVIDER=gemini`, `DEMO_MODE=false`, `JOBS_EAGER=false`, `REQUIRE_HUMAN_APPROVAL=true`, `ENVIRONMENT=production`. Set an explicit Gemini model available to your account; no model-availability claim is built into the app. Set exact HTTPS frontend origins in JSON `CORS_ORIGINS`. Database, Gemini, Redis, Resend and service-role secrets stay server-side.

Supabase Auth requires the project URL and public anon key. Configure allowed OAuth redirect URLs for the exact Vercel production origin and any explicitly approved preview origins. Avoid wildcard backend CORS. Tokens from another project/provider are rejected. Do not pass a service-role JWT as a student's token.

## Explicit release initialization

Run these with the intended hosted environment before starting API/worker traffic:

```sh
cd backend
alembic upgrade head
python -m app.manage indexes
python -m app.manage checkpoints
```

Run `migrations/supabase_rls.sql` separately in the Supabase SQL console as the schema owner. It enables owner-select policies and revokes direct client writes so clients cannot bypass application state/approval/email rules. It does not magically restrict a database owner/BYPASSRLS connection. Create a private runtime role, grant table access and add runtime-role policies as described in the SQL comments; never expose that role to a browser. Revoke UPDATE/DELETE/TRUNCATE on application_versions, application_approvals and audit_events from the runtime role, retaining SELECT/INSERT. Operators retain migration/maintenance permissions. Test these privileges in staging with the actual runtime credential.

Hosted startup performs no schema/index/checkpoint DDL. Local startup creates SQL tables/checkpoints for convenience; run Alembic anyway to record the migration revision and satisfy `/ready`. MongoDB writes and relational transactions are independent. Canonical IDs and retry-safe workflow steps reconcile duplicates; they are not a distributed transaction. Replaying notice confirmation after a partial failure reuses the canonical opportunity.

## Render and Vercel

Apply `render.yaml` after creating the environment group. Services are `opportunityos-api`, `opportunityos-worker` (concurrency 2) and **exactly one** `opportunityos-scheduler`. Keep the scheduler replica count at one. Docker context is backend and the API listens on `0.0.0.0:10000`. Render checks `/health` and deployment is configured for successful branch-main checks. Free/basic service availability and plan suitability must be confirmed in your own account; this repository does not claim an active deployment.

Vercel Root Directory: `frontend`. Runtime: Node **22.x**. Install: `npm ci`; build: `npm run build`. Copy `frontend/.env.vercel.example` into project environment variables and replace placeholders. `NEXT_PUBLIC_API_URL` ends in `/api`; persistent client calls must append `/v1/...`. The existing frontend screens and services are largely placeholders; configuring environment variables does not connect their demo actions to the persistent APIs. Never expose database, Gemini, Resend, Redis or Supabase service-role keys through NEXT_PUBLIC variables.

The container is nonroot. Docker Compose uses a separate root initialization service solely to set volume ownership and execute migrations; API and workers use UID 10001. Store local SQL/checkpoint files on the shared durable volume. Docker itself must be installed to run Compose.

## Verification after deployment

1. Check `/health` for process status and `/ready` for SQL migration-table access, configured MongoDB connectivity, and Redis when asynchronous delivery is enabled.
2. Obtain a real Supabase student token, call `/api/v1/auth/me`, and prove another user cannot read private resources.
3. Upload a small notice and resume, verify their jobs leave QUEUED and reach COMPLETED via a real worker, and confirm a reviewed notice.
4. Test application approval, material-change invalidation, stale revisions and idempotent user-reported submission. Inspect immutable rows with the runtime credential.
5. Verify Redis outage fails closed, broker delivery recovers, stale leases recover, and only one scheduler is active.
6. Inspect JWKS rotation, Atlas indexes, checkpoints and backups. Readiness does not prove workers, Gemini, Resend or Judge0 are available.

## Recovery, retention and observability

SQL jobs and outbox entries are durable. Delivery is at-least-once. Workers atomically claim a job, lease it for ten minutes, make at most three processing attempts, and fence completion by the attempt counter. Beat delivers the outbox every ten seconds, recovers stale jobs every minute, runs hourly reminders, and refreshes a bounded batch of verification analyses daily. `python -m app.manage dispatch` and `recover` are operator alternatives. Do not run a second permanent beat scheduler during recovery. Inspect DEAD_LETTER jobs and repair the cause before scheduling a new explicitly deduplicated operation; there is no unrestricted public dead-letter replay API.

Broker publication failures leave outbox records PENDING. Provider calls can already have occurred before a worker failure; at-least-once delivery is not exactly-once external execution. Resend receives stable event idempotency keys, but provider acceptance is not proof of delivery. Judge0 can create another isolated submission after a worker crash; it must enforce its own resource isolation and tenant protections. Cancellation is cooperative between bounded stages, not process preemption. SQL and MongoDB writes can partially succeed; retain IDs and retry/reconcile rather than assuming rollback across stores.

Do not retain resume contents and personal claims indefinitely. Upload bytes/text are stored in owner records and LangGraph checkpoints may contain profile claims. Define an operator retention/deletion and backup policy appropriate to the deployment. Production account deletion/export automation is not included.

Request failures log a request ID and exception class without payloads/provider strings. Configure `LOG_LEVEL` for your process logging. Install optional `requirements.observability.txt` only if desired; Sentry strips request, user, breadcrumb, exception and message payloads. OpenTelemetry instrumentation does not configure an exporter automatically. Supply and test a chosen SDK/exporter separately.

Hosted rate limiting uses Redis and fails closed on infrastructure failure. Forwarded client addresses must be sanitized by the trusted ingress; do not enable arbitrary proxy-header trust. Without forwarded-header trust, a proxy's peer address can produce a shared conservative rate bucket. Tune this at deployment and verify spoofing resistance.

Optional Judge0: independently deploy an isolated service, configure only Python/JavaScript language IDs, deny network in the sandbox, and explicitly set `JUDGE0_ISOLATION_CONFIRMED=true` only after isolation tests. The starter endpoint permits five queued code jobs per owner for the current deployment lifetime; server-owned hidden tests and bounded polling apply. No API/Celery process executes submitted code.

Optional AWS: install `requirements.aws.txt` only for adapters. Bedrock suggestions require AWS_ENABLED and a configured model/region. `aws-optional.yml` is manual OIDC/account preflight, not a provisioner or fake deployment. It validates the supplied role ARN/region and derives the account from STS; normal CI/release needs no AWS auth. AgentCore payload student IDs are never identity.

## Dependency maintenance

`pyproject.toml` loads its dependencies directly from `requirements.txt`. `requirements.lock.txt` pins the resolved environment; install requirements with the lock as constraints. Python 3.12 and 3.14 CI matrix checks portability, and Docker uses 3.14. The lock was resolved on Windows, with the Linux-only uvloop version pinned separately from registry metadata; target-platform installation remains part of CI. Do not describe this as a wheel/hash lock across all platforms. For a stricter supply-chain release, generate per-platform hash locks in the target image. After intentional updates, regenerate the lock from a clean environment, retain/resolve conditional platform pins, and run manifest validation, tests, Ruff, Bandit and pip-audit. The frontend scopes a fixed minimatch override to the lint parser; re-evaluate that override when its upstream constraint is updated. Never commit real `.env` files or local databases.

## API schema exports

From `backend/`, run `python scripts/export_api_contracts.py` to regenerate `docs/API_CONTRACTS.json` and `docs/openapi.json` from the implemented Python schema models and registered app. Tests are collected from `app/tests` by the project configuration. Launch the canonical entry point with `uvicorn main:app`.
