# AVSAR light opportunity-platform redesign

## Design changes
- Replaced the dark neo-brutalist landing page with a bright, clean opportunity-discovery homepage.
- Added a horizontal public navigation, prominent keyword/category search, discovery hero visual, category tiles, recommended listing cards and a four-step explanation of AVSAR.
- Reworked the workspace into a Unstop-inspired browsing shell with a pale-sage sidebar, search header, green active states and light opportunity cards.
- Replaced blue/purple styling with forest green, mint, sage, warm white, amber and peach.
- Updated opportunity cards and badges to fit the new visual system.
- Added responsive breakpoints for laptop, tablet and mobile widths.

## Functionality retained
- Existing Next.js routes and API service functions.
- FastAPI base URL and `/api/v1` integration.
- Supabase client and authentication hook.
- Demo/mock opportunity data, eligibility evaluation, resume analysis, application tracker, calendar export and profile screens.
- Category search links initialise the existing opportunities page filters from URL parameters.

## Important
- Sample opportunity records are fictional demo data. The redesigned UI does not imply live data collection or real trust verification.
- Frontend syntax and CSS structure were checked. A production build was not run in this environment because package dependencies are not installed here.
