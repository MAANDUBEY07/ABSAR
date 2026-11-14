# AVSAR Database Schema Specification

AVSAR uses MongoDB as the primary operational database, with Supabase managing authentication.

---

## Collections

### 1. `profiles`
Candidate user profile and demographic information.

```json
{
  "_id": "ObjectId",
  "auth_user_id": "UUID (from Supabase)",
  "name": "String",
  "email": "String",
  "phone": "String",
  "dob": "Date (YYYY-MM-DD)",
  "gender": "String ('Male', 'Female', 'Transgender', 'Other')",
  "category": "String ('General', 'OBC', 'SC', 'ST', 'EWS')",
  "domicile_state": "String",
  "domicile_district": "String",
  "annual_income": "Number",
  "differently_abled": "Boolean",
  "disability_percentage": "Number",
  "education": {
    "highest_degree": "String",
    "percentage": "Number",
    "passing_year": "Number",
    "institution": "String",
    "stream": "String"
  },
  "skills": ["String"],
  "resume_url": "String",
  "created_at": "ISODate",
  "updated_at": "ISODate"
}
```

### 2. `opportunities`
Aggregated schemes, scholarships, jobs, grants, and internships.

```json
{
  "_id": "ObjectId",
  "title": "String",
  "description": "String",
  "category": "String ('scholarship', 'government_scheme', 'internship', 'job', 'grant')",
  "provider": "String",
  "source_url": "String",
  "portal_source": "String",
  "deadline": "ISODate",
  "benefits_summary": "String",
  "criteria": [
    {
      "field": "String",
      "operator": "String",
      "value": "Any",
      "description": "String",
      "mandatory": "Boolean",
      "weight": "Number",
      "category": "String"
    }
  ],
  "min_score": "Number",
  "trust_score": "Number",
  "is_verified": "Boolean",
  "raw_notice_text": "String",
  "dedup_hash": "String",
  "created_at": "ISODate",
  "updated_at": "ISODate"
}
```

### 3. `applications`
Tracked candidate applications and deadline milestones.

```json
{
  "_id": "ObjectId",
  "user_id": "ObjectId (ref: profiles)",
  "opportunity_id": "ObjectId (ref: opportunities)",
  "status": "String ('saved', 'applied', 'interview_scheduled', 'shortlisted', 'rejected')",
  "applied_date": "ISODate",
  "deadline": "ISODate",
  "notes": "String",
  "created_at": "ISODate"
}
```

### 4. `trust_reports`
Audit reports for crawled opportunities assessing authenticity.

```json
{
  "_id": "ObjectId",
  "opportunity_id": "ObjectId (ref: opportunities)",
  "trust_score": "Number",
  "status": "String ('VERIFIED', 'SUSPICIOUS', 'UNVERIFIED')",
  "domain_is_official_gov": "Boolean",
  "duplicate_of_id": "ObjectId (optional)",
  "signals": ["String"],
  "audited_at": "ISODate"
}
```
