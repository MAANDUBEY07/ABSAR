# AVSAR Technical Architecture

## 1. System High-Level Architecture

```
[ Candidate / Beneficiary Browser ]
               │
               ▼
   [ Next.js Frontend (Tailwind + React) ]
               │
               ▼  REST API (/api/v1)
   [ FastAPI Backend Application ]
   ├── Authentication Middleware (Supabase JWT)
   ├── Routers (Profile, Opportunities, Eligibility, Resume, Trust)
   │
   ├── Core Services:
   │   ├── Eligibility Engine (Rule-based, 100% deterministic)
   │   ├── AI Extractor & Notice Parser (PDF/Doc OCR & LLM extraction)
   │   ├── Scraper & Duplicate Detector
   │   ├── Trust & Credibility Checker
   │   └── Resume Analyzer
   │
   └── Data Persistence:
       ├── MongoDB (Profiles, Opportunities, Applications, Trust Reports)
       └── Supabase Auth (Identity & User Credentials)
```

## 2. Key Modules & Design Decisions

### Rule-based Eligibility Engine
- Resides in `backend/app/services/eligibility_engine.py`.
- Completely deterministic without LLM hallucinations.
- Maps internal evaluation to four API contract statuses:
  - `ELIGIBLE`
  - `POTENTIALLY_ELIGIBLE`
  - `NOT_ELIGIBLE`
  - `CANNOT_DETERMINE`
- Distinguishes missing candidate data from unconfigured opportunity criteria.

### AI Extraction Pipeline
- Scraper collects raw circulars, notices, and portal postings.
- `ai_extractor.py` and `notice_parser.py` structure raw texts into standardized opportunities with criteria rules.
- `duplicate_detector.py` checks similarity and deduplicates against existing records.
- `trust_checker.py` flags official `.gov.in` / `.nic.in` domains, application fees anomalies, and authenticity signals.

### Frontend Application
- Next.js App Router for server/client component rendering.
- Role-driven navigation: dashboard, opportunity exploration, eligibility badges, deadline calendar, and resume matching.
