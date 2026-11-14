# AVSAR backend API

Launch from `backend/` with `uvicorn main:app --reload --port 10000`. Live OpenAPI is `/api/openapi.json`; interactive docs are `/docs`. The checked-in `openapi.json` is generated from the same application.

Persistent responses use `{"data": ..., "meta": {}}`. Private endpoints require a verified bearer token. Field errors omit sensitive input. `/api` compatibility is development-only; `/api/v1` is the hosted source of truth.

| Chart module | Implemented routes under `/api/v1` |
| --- | --- |
| `routes/profile.py` | GET/PUT `/profile` and `/profile/me` |
| `routes/opportunities.py` | GET/POST `/opportunities`, GET `/opportunities/{id}` |
| `routes/discovery.py` | GET `/discovery/feed`, POST `/discovery/jobs` |
| `routes/eligibility.py` | POST `/eligibility/check/{id}`, POST `/eligibility/batch`, matching/recommendation/explanation/feedback routes |
| `routes/resume.py` | POST `/resume/upload`, POST `/resume/match/{id}`, skills analysis/compare/gaps/roadmap/progress |
| `routes/trust.py` | GET `/trust/verify/{id}`, private verification analysis/history/report routes |
| `routes/applications.py` | Application creation/list/detail/analytics/update/approve/submit |
| `routes/calendar.py` | GET `/calendar`, `/calendar/events`, `/calendar/deadlines` |

Additional route modules retain authentication, notice review, documents, assessments, career planning, jobs and notifications from the rebuild requirements. Every listed chart route module is registered in the canonical `backend/main.py`; `app/main.py` retains compatibility with old imports.

`/eligibility/check` and `/eligibility/batch` adapt confirmed stored requirements to the original general engine and return its separate `api_status`: ELIGIBLE, POTENTIALLY_ELIGIBLE, NOT_ELIGIBLE or CANNOT_DETERMINE. Persistent `/recommendations` retains ELIGIBLE/INELIGIBLE/UNKNOWN. No executable custom rule or arbitrary regex is accepted by these HTTP routes. The full general engine remains available as a Python service.

Profile updates cannot change identity or notification email. Opportunity listing supports bounded `limit`/`offset`, category, search and exact location through the historical `state` parameter. Discovery feed returns ranked recommendations; discovery jobs accept only operator-configured public RSS feeds.

Resume upload returns 202 with durable job/document IDs. Resume matching requires `{"document_id":"YOUR_ANALYZED_DOCUMENT_ID"}` and uses only that owner's persisted resume claims. It does not infer years of employment. Trust verification returns deterministic risk evidence and UNKNOWN/EXPIRED employer status; it does not fabricate a verified-employer badge or a certainty score. Calendar events derive from the current owner's saved applications and supplied opportunity deadlines, with optional start/end date filters; no external calendar synchronization is claimed.

See [PERSISTENT_API.md](PERSISTENT_API.md) for payloads, application transitions, scoring formulas, uncertainty and job semantics. `API_CONTRACTS.json` contains schemas generated from the implemented Python models, including the separate eligibility vocabulary. See [OPERATIONS.md](OPERATIONS.md) for deployment, explicit migrations/index/checkpoint setup and security boundaries.
