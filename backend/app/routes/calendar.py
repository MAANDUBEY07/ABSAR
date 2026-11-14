"""Owner-scoped deadline events derived from saved applications."""

from datetime import date
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from app.routes.common import DB, Owner, Limit, Offset, ok
from app.models.application import Application
from app.repositories import documents

router = APIRouter()


@router.get("/calendar")
@router.get("/calendar/events")
@router.get("/calendar/deadlines")
def events(
    owner: Owner,
    db: DB,
    limit: Limit = 20,
    offset: Offset = 0,
    start: date | None = None,
    end: date | None = None,
):
    if start and end and start > end:
        raise HTTPException(422, "Calendar start must be on or before end")
    applications = list(
        db.scalars(
            select(Application)
            .where(Application.owner_id == owner)
            .order_by(Application.created_at, Application.id)
            .limit(501)
        )
    )
    result = []
    for application in applications[:500]:
        opportunity = documents.get("opportunities", application.opportunity_id)
        if not opportunity or not opportunity.get("deadline"):
            continue
        deadline = date.fromisoformat(opportunity["deadline"])
        if start and deadline < start or end and deadline > end:
            continue
        result.append(
            dict(
                id=application.id,
                application_id=application.id,
                opportunity_id=application.opportunity_id,
                title=opportunity["title"],
                deadline=deadline.isoformat(),
                application_status=application.status,
                source="APPLICATION_DEADLINE",
            )
        )
    result.sort(key=lambda item: (item["deadline"], item["id"]))
    return ok(
        result[offset : offset + limit],
        limit=limit,
        offset=offset,
        scanned=min(500, len(applications)),
        truncated=len(applications) > 500,
    )
