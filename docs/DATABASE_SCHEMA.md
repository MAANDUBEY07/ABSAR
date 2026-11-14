# AVSAR storage schema

`backend/app/config/database.py` provides the SQL engine/session and a single configured PyMongo client. Hosted storage is PostgreSQL + MongoDB; local development uses SQLite and a durable SQL document fallback. Settings are defined once in `app/config/settings.py`.

## Relational domain models

| Definition | Tables |
| --- | --- |
| `models/profile.py` | profiles, student_skills, education, student_preferences |
| `models/opportunity.py` | saved_opportunities; validated canonical opportunity document type |
| `models/resume.py` | user_documents; validated resume analysis and claim types |
| `models/application.py` | applications, application_versions, application_approvals, audit_events |
| `models/runtime.py` | jobs, integration_outbox, career_goals, career_milestones, assessments, assessment_attempts, notifications, notification_preferences, local_documents |

Owned rows share id, owner_id, payload, created_at and updated_at. Explicit indexed identifiers, foreign keys, unique keys and revision checks supplement the payload. Application material snapshots, approvals and audit events are append-only through application behavior, with runtime database permissions documented separately. `models/base.py` owns the single SQLAlchemy metadata/base; importing `app.models` registers all domain tables for Alembic.

## MongoDB collections

- opportunities: canonical SHA-256-derived IDs/fingerprints, explicit source facts, confirmed/unconfirmed requirements and UNKNOWN/EXPIRED employer status.
- raw_listings: source RSS facts captured during actual discovery.
- verification_results: private heuristic analyses and separately labeled user allegations.
- extracted_notices: owner draft/review/confirmation state with conservative provenance/evidence.
- skill_analysis: owner-scoped resume claims and quoted character offsets.
- agent_runs: owner-scoped completed career execution metadata.
- discovery_jobs: bounded RSS discovery results.
- opportunity_source_snapshots: supplied evidence snapshots for private analyses.

Unconfigured local MongoDB uses `local_documents(collection,id,payload)` in durable SQLite. Canonical opportunity IDs connect relational applications to the catalog. SQL and MongoDB writes are not a distributed transaction.

Uploads are owner-scoped by unique owner/content-hash records. Uploaded bytes are persisted in metadata payloads for the bounded worker parser; temporary `uploads/` files are gitignored. Define retention and backup/deletion policies before production.

Run `alembic upgrade head`, `python -m app.manage indexes`, and `python -m app.manage checkpoints` explicitly with operator credentials. Apply `migrations/supabase_rls.sql` separately in Supabase and verify the private runtime role. Hosted startup performs no DDL. See [OPERATIONS.md](OPERATIONS.md).
