# India opportunity discovery

The discovery page defaults to `country=India`. Users can choose **All countries**
to include the previous international feeds. The API remains backward compatible:
omitting `country` includes both Indian and international sources.

All eleven canonical categories have a source. Counts depend on current upstream
registrations; adapters never insert sample listings to fill an empty category.

| Source | Access | Coverage |
| --- | --- | --- |
| Unstop | Public JSON `/api/public/opportunity/search-result` | Indian jobs, internships, scholarships, hackathons, coding, innovation and startup challenges |
| Indian Government Jobs | Public RSS `/feeds/posts/default?alt=rss` | Apprenticeship and recruitment announcements |
| Scholarships.net.in | Public RSS `/feed` | Indian scholarship announcements |
| Opportunity Desk | Public WordPress JSON `/wp-json/wp/v2/posts?search=India` | Fellowships and funding with explicit India/worldwide eligibility evidence |
| ICSSR | Official public call page | India-based Senior Fellowship call; automatically excluded after its published deadline |
| Startup India / DPIIT | Official public programme pages | DPIIT recognition and Credit Guarantee Scheme for Startups |

No API key, paid subscription or additional deployment secret is required. The
official myScheme API requires authorization and was not integrated using an
undocumented key. Several RSS feeds tested during implementation were stale;
these were excluded.

## Geography, eligibility and availability

- Unstop structured Indian cities/states/countries are preserved in `location`.
  For jobs, `jobDetail.type` determines the work arrangement; `region=online`
  frequently describes registration rather than remote work.
- Remote listings advertised in INR on Unstop are labelled India-market remote
  listings. Currency does not confirm citizenship or individual eligibility.
- International fellowships and grants must mention India, worldwide eligibility,
  or countries across Asia and the Pacific in an eligibility section, and have a
  current explicit deadline. The original source remains the authority for all
  additional restrictions. India in unrelated article text is insufficient.
- Known closed, future-registration and expired Unstop listings are rejected.
  Registration deadline takes priority over the event's end date. Cached results
  are checked again on each read so passed deadlines do not remain visible.
- RSS entries older than 60 days and entries with a known expired deadline are
  excluded. If a publisher omits the deadline, it remains unknown. RSS sources
  are third-party publishers, not government verification; only short excerpts
  are displayed with attribution and a source link.
- Government programme pages are clearly marked **Programme information — check
  current application availability**. They are catalog entries, not evidence of
  an open application window. Eligibility remains unconfirmed for all providers.
- The registered ICSSR call URL is time-specific. Add subsequent official calls
  to the registry as they are published; the existing call disappears on expiry.

## Runtime behaviour

Provider requests use a fixed HTTPS host registry, reject redirects, limit response
size to 3 MiB, and have connection/read and elapsed retrieval budgets. At most
four source tasks run concurrently per snapshot. Each request has an independent
30-minute cache and lock, so simultaneous page and pagination requests share work.
Failures retry after 60 seconds and retain successful results for at most six hours,
subject to their deadlines. Successful empty responses replace previous results.
One unavailable provider does not erase another provider's results.

`meta.source_status` reports availability/stale fallback per source. The frontend
shows a partial-source notice on failures. All-category snapshots interleave
sources so the first page includes more than jobs. Provider IDs remain stable,
fit the application API contract, and work with details, eligibility and saving.

Example request:

```text
GET /api/v1/opportunities?country=India&category=hackathon&state=Karnataka&opportunity_mode=offline
```

Run deterministic tests with the existing CI command:

```powershell
python -m unittest discover -s backend/tests
```

Run an explicit live check from the repository root:

```powershell
python backend/scripts/check_india_sources.py --live
```
