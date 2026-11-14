# AVSAR / OpportunityOS

FastAPI backend for student profiles, opportunity matching, conservative risk analysis, resume claims, campus-notice review, versioned applications, practice assessments and career planning.

The checked-in reference had working general eligibility, fuzzy duplicate detection, PDF parsing and Gemini extraction utilities, alongside placeholder routes. Those utilities are retained, and the working backend now uses the requested `app/routes`, domain model/schema files, and `app/tests` layout. The persistent backend is a new implementation; compatibility assumptions and operational boundaries are recorded in [the capability report](docs/CAPABILITIES.md).

## Local backend

Python 3.12+ is required; the Docker image uses 3.14. From the repository root:

```sh
python -m venv .venv
# Activate .venv for your shell, then:
cd backend
pip install -r requirements.txt -c requirements.lock.txt
cp .env.example .env
alembic upgrade head
python -m app.manage indexes
python -m app.manage checkpoints
uvicorn main:app --reload --port 10000
```

PowerShell uses `Copy-Item .env.example .env` instead of `cp` if preferred. Install Tesseract separately for local OCR and add it to PATH; the Docker image includes it. Deterministic tests mock OCR and cloud services.

Open [interactive API docs](http://localhost:10000/docs) or [OpenAPI](http://localhost:10000/api/openapi.json). Persistent endpoints use `/api/v1`. Development signup/login live under `/api/auth`; use Supabase in hosted environments.

```sh
pytest -q
ruff check main.py app migrations scripts
ruff format --check main.py app migrations scripts
bandit -r main.py app -x app/tests -q
pip-audit -r requirements.lock.txt --no-deps --disable-pip
python scripts/validate_dependencies.py
```

`docker compose up --build` starts a local API, worker, one scheduler and Redis with durable SQLite storage. It performs explicit initialization in a separate service. Local eager jobs require no Redis; responses still return durable job IDs for long operations.

## Deployment and integration

- [Setup, migration, deployment and recovery guide](docs/OPERATIONS.md)
- [API payloads and semantics](docs/PERSISTENT_API.md)
- [Capability, assumptions and limitations report](docs/CAPABILITIES.md)
- [Recorded verification results](docs/VALIDATION.md)

Render services use an external `opportunityos-backend` environment group. Vercel uses Root Directory `frontend`, Node 22.x, `npm ci`, and `npm run build`. Environment examples contain placeholders only. No cloud accounts or live deployments are created by these files.
