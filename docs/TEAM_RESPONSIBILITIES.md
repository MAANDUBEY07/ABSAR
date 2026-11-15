# AVSAR – Hackathon MVP Team Responsibilities

This document defines the clear division of ownership across the 3 team members to ensure parallel, conflict-free development.

---

## Member 3: Frontend & User Experience Lead
**Focus Area:** Next.js Application, UI/UX, Component Library, State & Auth Integration

- **Primary Directories Owned:**
  - `frontend/src/app/**` (Pages: Dashboard, Opportunities, Resume, Applications, Profile)
  - `frontend/src/components/**` (Navbar, Sidebar, OpportunityCard, EligibilityBadge, TrustBadge, etc.)
  - `frontend/src/services/**` (`api.js`, `supabase.js`)
  - `frontend/src/hooks/**` (`useAuth.js`)
- **Key Responsibilities:**
  1. Build responsive, accessible UI in Tailwind CSS matching Figma/design wireframes.
  2. Implement Supabase client-side authentication and session management.
  3. Integrate frontend views with FastAPI endpoints defined in `docs/API_CONTRACTS.json`.
  4. Render 4-status eligibility badges (`ELIGIBLE`, `POTENTIALLY_ELIGIBLE`, `NOT_ELIGIBLE`, `CANNOT_DETERMINE`).
  5. Build the deadline calendar and application status tracker.

---

## Member 2: Backend Core & Eligibility Engine Lead
**Focus Area:** FastAPI Architecture, Database Layer, Eligibility Engine Integration, Security

- **Primary Directories Owned:**
  - `backend/app/main.py`
  - `backend/app/config/**` (`database.py`, `settings.py`)
  - `backend/app/models/**` & `backend/app/schemas/**`
  - `backend/app/routes/**` (`profile.py`, `opportunities.py`, `eligibility.py`, `applications.py`, `calendar.py`)
  - `backend/app/services/eligibility_engine.py` (Core Engine)
  - `backend/app/utils/**` (`auth.py`, `validators.py`)
  - `backend/app/tests/test_eligibility.py`
- **Key Responsibilities:**
  1. Setup FastAPI application routing, CORS, and dependency injection.
  2. Maintain SQLAlchemy owned records, PyMongo documents and local SQLite compatibility.
  3. Expose eligibility evaluation endpoints adhering to `docs/API_CONTRACTS.json`.
  4. Implement JWT / Supabase auth verification in `auth.py`.
  5. Maintain 100% test passing rate for core eligibility logic.

---

## Member 1: Data Ingestion, AI Extraction & Trust Checker Lead
**Focus Area:** Web Crawling, PDF/Notice Extraction, Deduplication, Trust Scoring, Resume Analysis

- **Primary Directories Owned:**
  - `backend/app/services/scraper.py`
  - `backend/app/services/notice_parser.py`
  - `backend/app/services/ai_extractor.py`
  - `backend/app/services/trust_checker.py`
  - `backend/app/services/duplicate_detector.py`
  - `backend/app/services/resume_analyzer.py`
  - `backend/app/routes/discovery.py`, `backend/app/routes/resume.py`, `backend/app/routes/trust.py`
  - `backend/tests/test_scraper.py`, `backend/tests/test_extractor.py`, `backend/tests/test_resume.py`, `backend/tests/test_trust.py`
- **Key Responsibilities:**
  1. Build scrapers to ingest opportunity postings from target portals and circulars.
  2. Implement PDF text extraction and structured parsing of criteria using LLM extractor.
  3. Implement deduplication pipeline to prevent redundant opportunities.
  4. Implement trust scoring algorithm (evaluating domain authenticity and scam signals).
  5. Implement resume parser to extract skills and compute opportunity match scores.


## Phase 2 coordination

Backend owns canonical API schemas and adapters; Member 1 owns algorithms; Member 3 owns frontend behavior. See INTEGRATION_CONTRACTS.md for the reconciled implementation boundaries and remaining review gates. Published feature branches remain preserved; cross-module integration fixes live on the dedicated integration branch.
