# Frontend API integration notes

- Added a centralized authenticated API client with envelope parsing, errors, and timeouts.
- Added Supabase session handling plus the backend's explicitly local-only development auth flow.
- Connected discovery, recommendations, opportunity detail, eligibility, source-signal review, resume upload/analysis, profile, applications, deadlines, and notifications to routes present in `backend/app/routes`.
- Added protected workspace navigation and loading, empty, and error states while retaining the existing light visual design.
- Kept the 11 canonical category values in frontend filters. Some current backend input schemas still enumerate a smaller set; this implementation does not change those schemas.
- The current backend's application lifecycle differs from the six product-facing labels. The UI maps labels to known backend states and only offers supported transitions.
- Hybrid opportunity filtering and ICS export are not implemented because the current API does not expose those capabilities.
