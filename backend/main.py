"""AVSAR FastAPI entry point. Run from backend: uvicorn main:app."""

import asyncio
from app.services.observability import configure
import logging
import time
from collections import OrderedDict
from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException
from redis import Redis
from app.config import settings
from app.config.database import engine, Session
from app.models.base import Base
from app.models.profile import Profile
from app.routes import (
    auth,
    profile,
    opportunities,
    discovery,
    eligibility,
    resume,
    trust,
    applications,
    notices,
    documents as document_routes,
    calendar,
    readiness,
    career,
    operations,
    legacy,
)

from app.repositories import documents

logging.getLogger("opportunityos").setLevel(settings.log_level)


@asynccontextmanager
async def lifespan(app):
    if not settings.hosted:
        Base.metadata.create_all(engine)
        from app.services.career import setup_checkpoints

        setup_checkpoints()
    if settings.postgres_startup_diagnostics:
        try:
            from app.utils.postgres_diagnostics import run_postgres_diagnostics

            await asyncio.to_thread(run_postgres_diagnostics, engine)
        except Exception:  # nosec B110
            # Even diagnostic import, cleanup or logging failures must not block startup.
            pass
    yield


app = FastAPI(
    title="AVSAR / OpportunityOS",
    version="1.0.0",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

local_rates = OrderedDict()
redis = Redis.from_url(settings.redis_url, socket_timeout=2, socket_connect_timeout=2)


def error(request, status, detail, code, headers=None):
    return JSONResponse(
        status_code=status,
        content=dict(
            detail=detail,
            error=dict(
                code=code, message=detail, request_id=getattr(request.state, "request_id", None)
            ),
        ),
        headers=dict(headers or {}, **{"X-Request-ID": getattr(request.state, "request_id", "")}),
    )


@app.exception_handler(StarletteHTTPException)
async def http_error(request, exc):
    return error(request, exc.status_code, exc.detail, f"HTTP_{exc.status_code}", exc.headers)


@app.exception_handler(IntegrityError)
async def relational_conflict(request, exc):
    return error(request, 409, "Concurrent update or resource conflict", "CONFLICT")


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    fields = [dict(location=list(e["loc"]), type=e["type"]) for e in exc.errors()]
    return JSONResponse(
        status_code=422,
        content=dict(
            detail=fields,
            error=dict(
                code="VALIDATION_ERROR",
                message="Invalid request fields",
                request_id=request.state.request_id,
            ),
        ),
    )


@app.middleware("http")
async def security(request: Request, call_next):
    request.state.request_id = str(uuid4())
    try:
        if request.url.path not in {"/", "/health", "/api/health", "/ready"}:
            address = request.client.host if request.client else "unknown"
            if settings.hosted:
                # Trust peer address only. Deploy behind a proxy configured to sanitize forwarded headers.
                key = f"rate:{address}:{int(time.time() // 60)}"
                try:
                    count = await asyncio.to_thread(
                        redis.eval,
                        "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n",
                        1,
                        key,
                    )
                except Exception:
                    return error(request, 503, "Rate limiter unavailable", "RATE_LIMIT_UNAVAILABLE")
            else:
                minute = int(time.time() // 60)
                count, previous = local_rates.get(address, (0, minute))
                count = count + 1 if previous == minute else 1
                local_rates[address] = (count, minute)
                local_rates.move_to_end(address)
                if len(local_rates) > 10000:
                    local_rates.popitem(last=False)
            if count > settings.rate_limit_per_minute:
                return error(
                    request, 429, "Rate limit exceeded", "RATE_LIMITED", {"Retry-After": "60"}
                )
        # Bound actual streamed request bodies, including multipart overhead.
        maximum = settings.max_upload_bytes + 65536
        if int(request.headers.get("content-length", "0")) > maximum:
            return error(request, 413, "Request exceeds upload limit", "UPLOAD_LIMIT")
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > maximum:
                return error(request, 413, "Request exceeds upload limit", "UPLOAD_LIMIT")
        request._body = bytes(data)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        if settings.jobs_eager and request.method == "POST" and response.status_code == 202:
            from starlette.background import BackgroundTask
            from app.services.jobs import dispatch

            response.background = BackgroundTask(dispatch)
        return response
    except Exception as exc:
        logging.getLogger("opportunityos").error(
            "Request failed request_id=%s error_type=%s",
            request.state.request_id,
            type(exc).__name__,
        )
        return error(request, 503, "Service temporarily unavailable", "SERVICE_UNAVAILABLE")


@app.get("/")
@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "opportunityos"}


@app.get("/ready")
def ready():
    try:
        with Session() as db:
            db.execute(select(Profile.id).limit(1))
            db.execute(text("SELECT version_num FROM alembic_version"))
        if documents.client:
            documents.client.admin.command("ping")
        if not settings.jobs_eager:
            redis.ping()
    except Exception:
        raise HTTPException(
            503, "Configured persistence or delivery infrastructure unavailable"
        ) from None
    return {
        "status": "ready",
        "scope": "Schema access, document store and broker connectivity; does not prove worker or provider availability",
    }


routers = [
    auth.router,
    profile.router,
    opportunities.router,
    discovery.router,
    eligibility.router,
    resume.router,
    trust.router,
    applications.router,
    notices.router,
    document_routes.router,
    calendar.router,
    readiness.router,
    career.router,
    operations.router,
]
for router in routers:
    app.include_router(router, prefix="/api/v1")
    app.include_router(
        router, prefix="/api", dependencies=[Depends(legacy.local_only)], include_in_schema=False
    )
app.include_router(legacy.router, prefix="/api")

configure(app, settings)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    expose_headers=["X-Request-ID"],
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=10000)
