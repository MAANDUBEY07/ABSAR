# AVSAR – Opportunity Discovery & Eligibility Platform

AVSAR is a hackathon MVP platform designed to bridge the gap between opportunities (government welfare schemes, scholarships, internships, grants, fellowships, and jobs) and aspiring beneficiaries (students, job seekers, citizens, and rural artisans).

## System Architecture Overview

- **Frontend**: Next.js (App Router), Tailwind CSS, Lucide Icons, Supabase Auth.
- **Backend**: FastAPI (Python), MongoDB / Motor, Pydantic, Rule-based Eligibility Engine.
- **AI & Automation**: Web Scraper, AI Document/Notice Extractor, Resume Analyzer, Trust & Credibility Checker.

## Repository Layout

```text
AVSAR/
├── docs/                 # System architecture, API contracts, database schemas, and team docs
├── backend/              # FastAPI application, eligibility engine, scrapers, analyzers
├── frontend/             # Next.js web application
└── .github/              # CI/CD workflows
```

## Getting Started

Refer to `docs/ARCHITECTURE.md` and `docs/TEAM_RESPONSIBILITIES.md` for team onboarding and local development instructions.


## Phase 2 integration baseline

The integration branch preserves the published backend, AI services and frontend histories. See [canonical integration contracts](docs/INTEGRATION_CONTRACTS.md), [endpoint inventory](docs/ENDPOINT_INVENTORY.md) and [verification report](docs/PHASE2_INTEGRATION_REPORT.md).

Local backend (Python 3.12+): create/activate a virtual environment, then from backend install `pip install -r requirements.txt -c requirements.lock.txt`, run `alembic upgrade head`, and start `uvicorn main:app --port 8000`. Default local authentication and eager jobs need no Redis. From frontend run `npm ci` and `npm run dev`; its default API base is http://localhost:8000/api/v1. `/auth/config` selects local or Supabase; no real secrets are checked in. Set real Supabase/Gemini settings only in private environment configuration.

Verification from backend: `python -m pytest -q`, `ruff check main.py app migrations scripts`, `bandit -q -r main.py app -x app/tests`, `python scripts/validate_dependencies.py`, `python scripts/export_stage1_contracts.py --check`, and `python scripts/smoke_phase2.py`. Frontend: `npm test`, `npm run lint`, `npm run build`. The HTTP smoke uses a private temporary database and closes its server. Cloud infrastructure and browser interactions have separate verification limits in the report.
