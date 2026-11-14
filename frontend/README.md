# AVSAR Frontend

Next.js frontend for the AVSAR student opportunity assistant.

## Run locally

```bash
npm install
Copy-Item .env.local.example .env.local   # PowerShell; create this file if it does not exist
npm run dev
```

Open http://localhost:3000.

## Current visual direction

AVSAR now uses a clean student-opportunity marketplace layout, taking structural cues from the supplied AVSAR discovery reference and Unstop's category-first browsing experience.

- Light warm-white canvas with deep forest-green text.
- Green, mint, sage, amber and peach accents. No blue or purple palette.
- Public discovery homepage with top navigation, hero search, category tiles, recommended opportunity cards and a four-step product explainer.
- Workspace uses a pale-sage sidebar, compact search header, rounded information cards and responsive page layouts.
- Opportunity categories, eligibility/trust indicators, saved opportunities, resume upload, application tracking, deadline calendar and profile screens remain in place.

## Backend connection

The existing API service layer, Supabase helper, auth hook and FastAPI endpoint paths are retained. Configure `.env.local` using `.env.local.example`. Keep `NEXT_PUBLIC_USE_MOCK_DATA=true` during frontend-only work; switch it to `false` once the FastAPI endpoints and Supabase project are ready.

The opportunity records currently shown in mock mode are fictional demo records. They are not live listings or verified opportunities.
