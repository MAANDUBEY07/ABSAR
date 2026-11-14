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
