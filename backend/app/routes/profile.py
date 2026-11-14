from fastapi import APIRouter
from sqlalchemy import delete
from app.routes.common import DB, Owner, ok
from app.models.profile import Profile
from app.models.profile import Skill
from app.models.profile import Education
from app.models.profile import Preference
from app.repositories.relational import owned
from app.schemas.profile import ProfileInput, ProfileResponse

router = APIRouter()


@router.get("/profile")
@router.get("/profile/me")
def profile(owner: Owner, db: DB):
    payload = owned(db, Profile, owner, owner).payload
    return ok(
        ProfileResponse.model_validate(
            dict(payload, id=owner, email=payload.get("notification_email"))
        ).model_dump(mode="json")
    )


@router.put("/profile")
@router.put("/profile/me")
def update_profile(body: ProfileInput, owner: Owner, db: DB):
    row = owned(db, Profile, owner, owner, lock=True)
    data = body.model_dump(mode="json")
    if data["skills"] is not None:
        data["skills"] = sorted({s.strip().casefold() for s in data["skills"] if s.strip()})
    row.payload = dict(data, notification_email=row.payload.get("notification_email"))
    for model, values in (
        (Skill, data["skills"] or []),
        (
            Education,
            [data["education"]]
            if isinstance(data["education"], dict)
            else (data["education"] or []),
        ),
        (Preference, [data["preferences"]]),
    ):
        db.execute(delete(model).where(model.owner_id == owner))
        for value in values:
            db.add(model(owner_id=owner, payload={"value": value}))
    db.commit()
    return ok(
        ProfileResponse.model_validate(
            dict(row.payload, id=owner, email=row.payload.get("notification_email"))
        ).model_dump(mode="json")
    )
