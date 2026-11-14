from fastapi import APIRouter, HTTPException
from app.routes.common import DB, Owner, Limit, Offset, ok
from app.schemas.opportunity import Discovery
from app.services.jobs import enqueue

router = APIRouter()


@router.post("/discovery/jobs", status_code=202)
def discovery(body: Discovery, owner: Owner, db: DB):
    from app.config import settings

    url = str(body.feed_url)
    if url not in settings.discovery_feeds:
        raise HTTPException(422, "Only operator-configured public RSS feeds are supported")
    job = enqueue(db, owner, "discovery", {"feed_url": url})
    return ok(dict(job_id=job.id, status=job.status))


@router.get("/discovery/feed")
def feed(owner: Owner, db: DB, limit: Limit = 20, offset: Offset = 0):
    from app.routes.eligibility import recommendations

    return recommendations(owner, db, limit=limit, offset=offset)
