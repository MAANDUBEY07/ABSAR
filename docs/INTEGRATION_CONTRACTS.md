# AVSAR Phase 2 canonical integration contracts

These are the backend-owned implementation contracts on codex/avsar-phase2-integration, reconciled against published Member 1 77d9c91, Member 3 5444c98 and backend 32777e8. This records code-level coordination and decisions, not an assertion of separate human sign-off or release approval. Published member branches are preserved. Main is not modified.

## Categories, modes and source data

Canonical categories: scholarship, internship, job, government_scheme, fellowship, apprenticeship, hackathon, coding_competition, innovation_challenge, startup_challenge, grant. Member 1 ExtractedOpportunity and ScrapedOpportunity, backend OpportunityInput, and frontend constants agree. Mode is online/offline/hybrid/null; category_metadata is source JSON. Legacy coding_challenge projects coding_competition without changing historical IDs. Legacy research remains distinct pending manual classification. remote=true can project online; remote=false does not distinguish offline from hybrid.

Backend rejects ambiguous manual date input; AI drafts retain null with a warning when a source deadline is ambiguous. Dates are never guessed. Source attribution, retrieval time and raw scraped provenance survive ingest_scraped. Public source observations are append-only, keyed by the canonical identity plus normalized observed payload; new metadata never silently overwrites earlier facts. Exact fingerprint identity is stable. Member 1 SHA/fuzzy comparisons create review records, including exact duplicate observations. Suspected duplicates remain separate records: there is no automatic merge or deletion. Candidate review scans are currently bounded to 500 and disclose truncation; production-scale indexing is a follow-up.

GET /api/v1/opportunities/{id}/observations and /duplicates provide bounded limit/offset access. Existing create/detail APIs remain compatible. No source URL supplied by a user is executed by these retrieval endpoints.

## Eligibility and profile demographics

Both recommendation matching and eligibility endpoints use the same deterministic EligibilityEngine decision. Unconfirmed requirements always produce unknown/CANNOT_DETERMINE, even when preliminary criteria would fail. confirmed=true with no requirements means the reviewer explicitly confirmed no restrictions and yields ELIGIBLE. Never set confirmed automatically on AI extraction. Missing mandatory facts remain UNKNOWN; NOT UNKNOWN is UNKNOWN; AND/OR use three-valued logic. Public api_status: ELIGIBLE, POTENTIALLY_ELIGIBLE, NOT_ELIGIBLE, CANNOT_DETERMINE. Recommendation eligibility maps these to ELIGIBLE, UNKNOWN, INELIGIBLE, UNKNOWN respectively and retains eligibility_detail. Expired opportunities are not recommendable.

Explicit optional typed requirement fields: min_age, max_age, max_annual_income, genders, social_categories, domicile_states, required_disability_status, plus existing academic/location/skill/experience fields. Values are supplied by a reviewed source, never inferred from category or free text. DOB/gender/category/domicile/income/disability profile facts are owner-protected and missing facts stay unknown. The profile page preserves these fields during PUT even when it does not offer an input control for every demographic field. Collect sensitive information only for relevant chosen eligibility checks. Source text is not executable policy or user regex.

## Resume contract

Member 1 callable: analyze_resume(resume_input: str|bytes, opportunity=None) -> ResumeAnalysisResult. Backend worker passes bounded extracted text and sets owner_id/document_id itself. Adapter preserves parsed_skills, education, experience_years, readiness_score and recommendations. Backward-compatible skills/evidence/disclaimer remain; claims evidence is lexical and can be a subset of taxonomy-normalized skills. Estimates are rule-based and unverified. No Gemini resume scoring, fabricated qualifications or automatic profile mutation. Legacy mocked three-argument adapters are accepted only at their existing validated boundary; production uses the published callable.

POST /api/v1/resume/upload multipart file -> 202 data:{document_id,job_id,status}. GET /api/v1/jobs/{job_id}/result -> data:{id,status,attempts,result,error}. Result is null until available; backend ownership protects both documents and jobs. States: QUEUED,RUNNING,RETRY,COMPLETED,DEAD_LETTER,CANCELLED. Frontend polls this endpoint and displays real result fields, warnings and disclaimer. Absence of extracted employment evidence does not prove no experience.

## Trust contract and read-only retrieval

Member 1 check_opportunity_trust(dict) -> source assessment with trust_score, status VERIFIED/UNVERIFIED/SUSPICIOUS, signals, official_domain_match and indicator lists. Backend retains independent risk_score/risk_level/evidence/disclaimer and UNKNOWN/EXPIRED verification_status. Full Member 1 output is under source_assessment. Scores are not blindly inverted or equated. Official-domain matching is a heuristic, not proof that claims/employers are legitimate. Risk signals are not proof of fraud.

GET /api/v1/trust/verify/{id} and verification history are read-only. Missing analysis returns 404. An explicit POST /api/v1/verification/analyze {opportunity_id} creates a private analysis/snapshot. Frontend's user-triggered Review source signals action uses POST. Badge distinguishes expiry, risk review, official-domain match and unverified. Errors remain error states. Explicit denials of OTP/guaranteed placements do not count as affirmative requests. Negation does not suppress later affirmative requests in the same sentence.

## Ingestion, notices and workers

Configured AI PDF notice processing: upload -> durable job -> existing parse_pdf -> existing extract_opportunity -> normalization -> NEEDS_REVIEW -> explicit confirmation -> catalog/observations/duplicate review. AI analysis never publishes or verifies automatically. Deterministic local notice mode is explicitly labeled DETERMINISTIC_TEXT_EXTRACTION. Scanned PDFs with no extractable text in the AI path fail honestly; OCR/human handling is required. Non-PDF AI notice processing remains unsupported rather than pretending completion. Human confirmation whitelists OpportunityInput fields from the diagnostic draft.

Lease recovery now synchronizes associated notices to RETRY or FAILED and clears the stale lease. Completed/confirmed results are protected by conditional transitions. SQL jobs and Mongo documents are not a distributed transaction; crash/outage reconciliation still needs hosted testing.

RSS remains configured via DISCOVERY_FEEDS. GET /api/v1/discovery/sources lists only operator-enabled Member 1 sources. POST /api/v1/discovery/sources/{source_id}/jobs queues registered source work; enable IDs through DISCOVERY_SOURCES. No arbitrary URL override is exposed. Registered adapters use pinned public DNS/TLS/redirect/body checks through safe_fetch, plus source throttling. Their normalized output enters the same catalog observation/fuzzy review pipeline. Feed/source refresh deduplication reuses active jobs but permits a new terminal-job refresh.

Verification maintenance now pages through records and ignores allegations as analysis inputs, rather than permanently using the first 100. Reminders retain fair paging. Hosted cancellation is cooperative and cannot recall an already-started external call.

## API envelopes, pagination and authentication

Canonical prefix /api/v1. Success {data,meta}; errors {detail,error:{code,message,request_id}}. Field validation detail contains locations/types. Health/readiness and legacy local token responses are documented exceptions. Frontend requestPage preserves meta; single-result request unwraps data. limit/offset are bounded. Existing recommendation/calendar scans still cap at 500 with truncated metadata; observation/duplicate APIs filter before pagination. Trust history remains bounded to 501 matching records.

Only local and Supabase are active. Frontend config comes from /auth/config; local tokens never override a selected Supabase session. Supabase refresh/signout uses the provider. Issuer/audience/signature/expiry/role/sub checks and owner predicates remain. Local signup/login are development /api/auth routes with direct token responses. JWT logout does not revoke an already-issued token; client clears token/provider session. No credentials are placed in frontend code.

## Application lifecycle and explicit submission

SAVED -> DRAFT -> READY_FOR_REVIEW -> APPROVED -> SUBMITTED, followed by supported assessment/interview/offer/rejected/withdrawn transitions. Actual allowed edges remain backend service.TRANSITIONS, mirrored by frontend constants. Prepare does not approve. Review displays saved material. Approve is an explicit POST /applications/{id}/approve with current revision. Submit is a separate confirmation plus POST /applications/{id}/submit {revision,confirmation:true} and Idempotency-Key. Client retains the same key for retries of the same application/revision. No-op repeated submissions do not create duplicates. Receipt remains USER_REPORTED and external_submission_verified=false. Updating material invalidates approval; submitted material is immutable. Conflicts return 409 and frontend reloads.

## Verification and scope

See PHASE2_INTEGRATION_REPORT.md for exact tests and limitations. Generated API_CONTRACTS.json/openapi.json and ENDPOINT_INVENTORY.md are exported from current code; --check detects drift. Backend owns contract validation, Member 1 owns algorithms, Member 3 owns UI/provider behavior. Minimal cross-module changes implement these compatible boundaries; algorithm implementations and visual identity are retained. Human release review and hosted provider verification remain required before merging main.
