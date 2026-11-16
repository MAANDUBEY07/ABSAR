# AVSAR REST API Documentation

This document describes the agreed REST API endpoints for the AVSAR backend service.

Base URL: `/api/v1`

---

## 1. Authentication & Profiles (`/api/v1/profile`)

- **GET `/api/v1/profile/me`**
  - Headers: `Authorization: Bearer <token>`
  - Returns current user's profile details.
- **PUT `/api/v1/profile/me`**
  - Updates profile demographics (dob, gender, category, domicile, annual_income, skills, education).

---

## 2. Opportunities & Discovery (`/api/v1/opportunities`, `/api/v1/discovery`)

- **GET `/api/v1/opportunities`**
  - Query parameters: `category`, `state`, `search`, `opportunity_mode`, `offset`, `limit`.
  - Filters combine before pagination. `state` is a case-insensitive partial location match. `opportunity_mode` accepts `online`, `offline`, or `hybrid`; records with unknown modes are excluded when a mode is selected. Live listings use this endpoint; recommendations remain a separate personalized workflow.
  - Returns paginated list of active opportunities.
- **GET `/api/v1/opportunities/{id}`**
  - Returns detailed opportunity specifications and criteria.
- **GET `/api/v1/discovery/feed`**
  - Returns opportunities ranked and personalized for the authenticated candidate.

---

## 3. Eligibility Engine (`/api/v1/eligibility`)

- **POST `/api/v1/eligibility/check/{opportunity_id}`**
  - Evaluates authenticated candidate profile against the opportunity.
  - Returns `EligibilityEvaluationResponse` with one of the four contract statuses:
    - `ELIGIBLE`
    - `POTENTIALLY_ELIGIBLE`
    - `NOT_ELIGIBLE`
    - `CANNOT_DETERMINE`
- **POST `/api/v1/eligibility/batch`**
  - Batch evaluates candidate profile against multiple opportunities.

---

## 4. Resume Analyzer (`/api/v1/resume`)

- **POST `/api/v1/resume/upload`**
  - Uploads PDF/DOCX resume file.
  - Extracts skills, education, and career experience.
- **POST `/api/v1/resume/match/{opportunity_id}`**
  - Matches resume text against opportunity description and generates gap analysis.

---

## 5. Trust & Authenticity (`/api/v1/trust`)

- **GET `/api/v1/trust/verify/{opportunity_id}`**
  - Returns trust score, verified status, and credibility signals (domain verification, duplicate flags, official Gazette notice check).

---

## 6. Applications & Deadlines (`/api/v1/applications`, `/api/v1/calendar`)

- **GET `/api/v1/applications`**
  - Returns user tracked applications and status (`saved`, `applied`, `shortlisted`, `rejected`).
- **POST `/api/v1/applications`**
  - Adds opportunity to user tracker.
- **GET `/api/v1/calendar/deadlines`**
  - Returns upcoming application deadlines and milestones for the calendar widget.
