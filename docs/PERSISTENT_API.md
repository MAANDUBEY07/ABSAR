# Persistent API

`/api/v1` is the hosted source of truth. `/api/openapi.json` lists exact request schemas; `/docs` is interactive. Send `Authorization: Bearer ACCESS_TOKEN` on private endpoints. Successes use `{"data": ..., "meta": {}}`. Errors preserve `detail` and add `error.code`, `error.message`, and `error.request_id`; validation errors list locations/types without reflecting input. Unexpected failures return a generic 503.

Authentication config is public. `/auth/me` synchronizes the signed identity with a profile. `/auth/logout` tells the client to clear its session; it does not revoke already-issued JWTs. Use provider logout too. Supabase uses configured-project asymmetric JWKS, `authenticated` audience/role and UUID subjects. Cognito compatibility accepts configured-pool **ID tokens**, not arbitrary access tokens. Local signup/login are development-only, use scrypt and issue 30-minute tokens. There are no Supabase passwords in application storage.

## Example student journey

1. Development only: `POST /api/auth/signup` with `{"email":"student@example.test","password":"replace-with-long-local-password"}`. Production obtains tokens from Supabase instead.
2. `PUT /api/v1/profile`:

```json
{
  "name": "Student",
  "degree": "BTech",
  "branch": "Computer Science",
  "cgpa": 8.1,
  "graduation_year": 2027,
  "skills": ["python", "sql"],
  "experience_months": 0,
  "education": [{"institution": "User-supplied institution", "degree": "BTech"}],
  "preferences": {"remote": true, "min_stipend": 5000}
}
```

This is replacement semantics for editable profile fields. Absent scalar facts remain null; no experience is derived from skills. Identity and notification email cannot be edited. Normalized skills, education and preferences persist alongside the profile.

3. `POST /api/v1/opportunities`:

```json
{
  "title": "Backend internship",
  "category": "internship",
  "organization": "User-supplied organization",
  "application_url": "https://example.org/apply",
  "description": "Opportunity details supplied by the user",
  "remote": true,
  "stipend": 10000,
  "requirements": {
    "confirmed": true,
    "degrees": ["BTech"],
    "min_cgpa": 7,
    "required_skills": ["python"],
    "preferred_skills": ["docker"],
    "min_experience_months": 0
  }
}
```

The title, organization, canonical application URL and deadline determine a stable SHA-256 fingerprint/ID. Reinsertions preserve the first record. `confirmed` means the submitted requirements were explicitly supplied/confirmed; it is not employer verification. Canonical opportunities form a shared public catalog. Private analyses, reports, notices, documents and jobs remain owner-scoped.

4. `POST /recommendations/match` with `{"opportunity_id":"ID"}`. `GET /recommendations` supports `remote`, `max_duration_months`, `min_stipend`, `domain`, `graduation_year`, minimum `deadline`, `verification_status`, `limit` (1–100), and `offset` (0–10000). Scanning stops at 500 and reports truncation. Explanations are recomputed from current profile/catalog state. Feedback accepts `relevant`, `not_relevant`, or `saved`.
5. `POST /verification/analyze` with the opportunity ID; GET latest/history under `/verification/ID`. `POST /verification/report` adds a private allegation with `reason`; it does not mark fraud as proven.
6. Upload a PDF/DOCX as multipart field `file` to `/skills/analyze-resume`. HTTP 202 returns `job_id` and `document_id`. Poll `/jobs/JOB_ID`; inspect `data.result` only after `COMPLETED`. Evidence quotes use offsets in extracted text. `/skills/compare` and `/skills/roadmap` accept an opportunity ID and optional explicitly supplied skills. GET gaps requires `opportunity_id`; progress lists owner analyses. Skills are never copied silently into a profile.
7. Notices: multipart upload to `/notices/upload`, POST `/notices/ID/extract` (202), poll status/job, review the conservative draft, then POST `/notices/ID/confirm` with a complete `OpportunityInput`. Draft ISO dates require explicit deadline context. Confirmation reuses/creates the canonical catalog record and does not verify the employer.
8. Applications: create with `{"opportunity_id":"ID","material":{"answer":"My claim"}}`. Initial status is `SAVED`, revision 1. PATCH with the current revision to `DRAFT`, then `READY_FOR_REVIEW`. POST `/applications/ID/approve` with `{"revision":3}` binds the authenticated owner to the immutable revision-3 material digest and produces revision 4. POST `/applications/ID/submit` with `{"revision":4,"confirmation":true}` and header `Idempotency-Key: student-submission-001` produces a user-reported receipt. Retry the identical request/key for the original receipt. Reuse for another request returns 409. No employer portal is contacted.
9. Assessments: POST `/readiness/assessment` with kind `aptitude`, `interview`, or `coding`; GET `/readiness/questions?assessment_id=ID`; POST `/readiness/submit-answer` with assessment ID, question ID and answer. Attempts are immutable, including retries with different answers. Interview responses receive a human-review rubric. `/readiness/execute-code` returns 503 until independent Judge0 isolation and allowed Python/JavaScript IDs are configured; configured runs return a persistent job ID. Tests and accepted answers are not returned.
10. POST `/career-agent/start` with `{"goal":"Become a backend developer"}`; poll its job and GET `/career-agent/ID`, `/plan`. Message, pause, resume, cancel and milestone completion endpoints persist owner state. Text messages cannot approve applications. Suggested drafts are proposals requiring separate human review, not submitted applications.
11. GET `/notifications`; PATCH `/notifications/preferences` with IANA timezone, quiet-start/end hours and channels (`in_app`, opt-in `email`). Only signed identity claims supply an email recipient.

## Matching formulas and uncertainty

The persistent vocabulary is `ELIGIBLE`, `INELIGIBLE`, `UNKNOWN`. A failed mandatory criterion makes a record ineligible even with a high score. Missing relevant facts or an unconfirmed requirement set retain uncertainty. A skill list explicitly supplied as empty is different from an unknown skill list.

| Factor | Formula used by this rebuild |
| --- | --- |
| skills, weight 0.40 | 100 × matched required / total required; null without a required denominator or known student skills |
| preferences, weight 0.25 | Percentage of available remote/domain/stipend/duration preference checks passed; null with no comparable preferences |
| experience, weight 0.20 | min(100, 100 × known months / required months); explicit zero-month requirement gives 100; null when either fact is absent |
| learning, weight 0.15 | Percentage of preferred skills missing from a known student skill list; null without preferred denominator or known student skills |

Unavailable factors contribute zero; weights are never renormalized. Data coverage is the sum of weights with available factors. All four nonnegative finite weights must sum to 1. The reference checkout did not contain a persistent matching implementation, so the latter three formulas are documented assumptions rather than claims of exact reproduction. Learning reflects potential learning gaps, not demonstrated proficiency. The reusable general eligibility engine retains its separate internal and external status vocabularies.

## Bounds and job semantics

Uploads: 5 MiB; 30 PDF pages; 16 million image pixels; 20 MiB expanded DOCX; 100,000 extracted characters. Standalone `notice_parser.py` keeps its separate historical 15 MiB utility limit; persistent uploads use stricter validation. OCR runs only in the worker/eager job executor. Scanned documents require Tesseract. The standalone Gemini extractor keeps its 30,000-character utility limit and requires a configured model; persistent notice extraction currently uses deterministic conservative drafts.

Jobs expose QUEUED/RUNNING/RETRY/COMPLETED/DEAD_LETTER/CANCELLED. A 202 response is acceptance, not proof of completed work. Cancellation is cooperative; it does not undo a provider request or an already committed document write. Refreshes, reminders and discovery operate in bounded batches. RSS discovery only accepts operator-configured `DISCOVERY_FEEDS`, uses safe XML and public pinned DNS fetching, and reads at most 50 items per job.
