# AVSAR backend architecture

The working backend follows the supplied chart. `backend/main.py` contains the FastAPI instance, middleware, safe errors, health/readiness and router registration. `app/main.py` is a compatibility import for that same instance.

```text
backend/
  main.py
  requirements.txt
  .env.example
  app/
    config/       settings.py, database.py
    models/       profile.py, opportunity.py, resume.py, application.py, trust_report.py
    schemas/      profile.py, opportunity.py, eligibility.py, resume.py, trust.py, application.py
    routes/       profile.py, opportunities.py, discovery.py, eligibility.py,
                  resume.py, trust.py, applications.py, calendar.py
    services/     ai_extractor.py, notice_parser.py, scraper.py, resume_analyzer.py,
                  eligibility_engine.py, trust_checker.py, duplicate_detector.py
    utils/        auth.py, file_handler.py, validators.py
    tests/        test_scraper.py, test_extractor.py, test_eligibility.py,
                  test_resume.py, test_trust.py, and the full API/security regression suite
  uploads/        gitignored temporary-file directory
```

Those modules contain real implementations. The former `app/api` implementation has moved to `app/routes`. `utils/auth.py` verifies the selected provider. `utils/file_handler.py` validates and extracts bounded PDF/DOCX/images; `services/resume_analyzer.py` identifies quoted skill claims. `services/scraper.py` is the limited public RSS connector. `services/trust_checker.py` implements conservative deterministic evidence rules.

Additional source files are intentional support for the earlier complete-backend requirements: shared base/runtime models and schemas, repositories, notice/auth/career/readiness/operations routers, job/outbox services, LangGraph checkpoints, worker/operator commands, migrations, dependency constraints, Docker and deployment files. Removing those would remove required persistence or workflows. `models/persistent.py` and `schemas/persistent.py` retain import compatibility while domain definitions live in the chart's named files; they do not define duplicate mapped tables/settings. `services/risk.py` and `services/documents.py` are compatibility aliases to their named implementations.

Storage remains PostgreSQL for transactional owned records and MongoDB for flexible catalog/analysis documents. `config/database.py` owns the SQL engine/session and one PyMongo connection. Local development uses SQLite and a durable document-table fallback. This hybrid storage preserves application revision/approval/job guarantees; a file-tree comment about MongoDB does not convert transactional data into an unsafe cross-store transaction.

All private access uses the authenticated owner. Long operations return persistent job IDs and run through SQL outbox + Celery; one beat scheduler handles delivery/recovery/reminders/refresh. Models can suggest learning steps but cannot approve applications, establish facts or execute code locally. See [CAPABILITIES.md](CAPABILITIES.md) for operational limits and [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) for actual storage.
