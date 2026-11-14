# AVSAR Frontend

Next.js 14 App Router frontend for the AVSAR student opportunity platform. The existing light green visual system is retained.

## Run locally

```powershell
npm install
Copy-Item .env.local.example .env.local
npm run dev
```

Open http://localhost:3000. Start the FastAPI backend separately and set `NEXT_PUBLIC_API_BASE_URL` to its `/api/v1` base URL.

## Authentication

The frontend reads `/api/v1/auth/config` before initializing authentication. When the backend uses Supabase, configure `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`; the Supabase browser client persists and refreshes its session. The anon key is public configuration. Never put a Supabase service-role key or another private secret in a `NEXT_PUBLIC_` variable.

When the backend explicitly reports its local development auth provider, the login and signup pages use the backend's development-only `/api/auth/login` and `/api/auth/signup` routes. That short-lived token is held in `sessionStorage`. Hosted environments must use the configured external provider.

## Backend-connected workflows

- Opportunity search, canonical category filters, pagination, details, and saving to the application tracker.
- Personalized recommendations, eligibility checks, profile editing, deadline events, notifications, and source risk-signal review.
- PDF/DOCX resume upload, job polling, extracted skill claims, and opportunity-specific skill comparison.

Requests use a centralized client that attaches the authenticated bearer token, parses `data`/`meta` envelopes, reports API errors, and applies request timeouts. No demo listings are used as a substitute for backend data.

The backend currently exposes application lifecycle states such as `SAVED`, `DRAFT`, `READY_FOR_REVIEW`, `SUBMITTED`, `ASSESSMENT`, `INTERVIEW`, and `OFFER`. The UI maps these to student-facing labels. It only sends status transitions accepted by the current backend; the six-state product vocabulary is not a direct match to the present API schema.

Opportunity mode filtering uses the authenticated recommendations endpoint, which supports `remote=true/false`. Hybrid mode is not exposed because the current backend schema does not define it. The backend calendar API does not provide ICS export.
