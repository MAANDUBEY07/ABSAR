"""MongoDB hosted; durable SQL document table locally. No cross-store transaction."""

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.config.database import Session, mongo_client
from app.models.runtime import LocalDocument

COLLECTIONS = (
    "opportunities",
    "opportunity_observations",
    "duplicate_reviews",
    "raw_listings",
    "verification_results",
    "extracted_notices",
    "skill_analysis",
    "agent_runs",
    "discovery_jobs",
    "opportunity_source_snapshots",
)
client = mongo_client


def put(collection, record_id, payload, insert_only=False):
    document = dict(payload, id=record_id)
    if client:
        col = client[settings.mongodb_database][collection]
        col.update_one(
            {"_id": record_id}, {"$setOnInsert" if insert_only else "$set": document}, upsert=True
        )
        return get(collection, record_id)
    try:
        with Session.begin() as db:
            existing = db.get(LocalDocument, (collection, record_id))
            if existing is None:
                db.add(LocalDocument(collection=collection, id=record_id, payload=document))
            elif not insert_only:
                existing.payload = document
            else:
                return existing.payload
    except IntegrityError:
        if insert_only:
            return get(collection, record_id)
        raise
    return document


def get(collection, record_id, owner=None):
    if client:
        query = {"_id": record_id}
        if owner is not None:
            query["owner_id"] = owner
        result = client[settings.mongodb_database][collection].find_one(query, {"_id": 0})
    else:
        with Session() as db:
            row = db.get(LocalDocument, (collection, record_id))
            result = row.payload if row else None
    if result and owner is not None and result.get("owner_id") != owner:
        return None
    if result and collection == "opportunities":
        from app.integrations.normalization import opportunity_view

        result = opportunity_view(result)
    return result


def _scan(collection, limit=501, owner=None):
    if client:
        query = {"owner_id": owner} if owner is not None else {}
        return list(
            client[settings.mongodb_database][collection]
            .find(query, {"_id": 0})
            .sort("_id", 1)
            .limit(limit)
        )
    with Session() as db:
        query = select(LocalDocument).where(LocalDocument.collection == collection)
        if owner is not None:
            query = query.where(LocalDocument.payload["owner_id"].as_string() == owner)
        return [r.payload for r in db.scalars(query.order_by(LocalDocument.id).limit(limit))]


def indexes():
    if client:
        for name in COLLECTIONS:
            client[settings.mongodb_database][name].create_index([("owner_id", 1), ("id", 1)])
        client[settings.mongodb_database].opportunities.create_index("fingerprint", unique=True)


def transition(collection, record_id, owner, expected_statuses, changes):
    """Update an owned document only while its current state permits the transition."""
    if client:
        result = client[settings.mongodb_database][collection].update_one(
            {"_id": record_id, "owner_id": owner, "status": {"$in": list(expected_statuses)}},
            {"$set": changes},
        )
        return result.matched_count == 1
    # Optimistic full-payload comparison prevents lost updates in the SQL fallback.
    with Session.begin() as db:
        row = db.get(LocalDocument, (collection, record_id))
        if (
            not row
            or row.payload.get("owner_id") != owner
            or row.payload.get("status") not in expected_statuses
        ):
            return False
        before = row.payload
        result = db.execute(
            update(LocalDocument)
            .where(
                LocalDocument.collection == collection,
                LocalDocument.id == record_id,
                LocalDocument.payload == before,
            )
            .values(payload=dict(before, **changes)),
            execution_options={"synchronize_session": False},
        )
        return result.rowcount == 1


def verification_history(owner, opportunity_id, limit=501):
    if client:
        return list(
            client[settings.mongodb_database]
            .verification_results.find(
                {"owner_id": owner, "opportunity_id": opportunity_id}, {"_id": 0}
            )
            .sort([("analyzed_at", -1), ("_id", -1)])
            .limit(limit)
        )
    with Session() as db:
        query = (
            select(LocalDocument)
            .where(
                LocalDocument.collection == "verification_results",
                LocalDocument.payload["owner_id"].as_string() == owner,
                LocalDocument.payload["opportunity_id"].as_string() == opportunity_id,
            )
            .order_by(
                LocalDocument.payload["analyzed_at"].as_string().desc(), LocalDocument.id.desc()
            )
            .limit(limit)
        )
        return [row.payload for row in db.scalars(query)]


def scan(collection, limit=501, owner=None):
    rows = _scan(collection, limit, owner)
    if collection == "opportunities":
        from app.integrations.normalization import opportunity_view

        return [opportunity_view(row) for row in rows]
    return rows


def iterate(collection, batch_size=100):
    """Stable bounded-memory sweep across initial records, not the first batch forever."""
    if client:
        cursor = (
            client[settings.mongodb_database][collection]
            .find({}, {"_id": 0})
            .sort("_id", 1)
            .batch_size(batch_size)
        )
        yield from cursor
        return
    with Session() as db:
        maximum = db.scalar(
            select(LocalDocument.id)
            .where(LocalDocument.collection == collection)
            .order_by(LocalDocument.id.desc())
            .limit(1)
        )
    after = ""
    while maximum:
        with Session() as db:
            page = list(
                db.scalars(
                    select(LocalDocument)
                    .where(
                        LocalDocument.collection == collection,
                        LocalDocument.id > after,
                        LocalDocument.id <= maximum,
                    )
                    .order_by(LocalDocument.id)
                    .limit(batch_size)
                )
            )
            records = [row.payload for row in page]
            if not page:
                break
            after = page[-1].id
        yield from records


def related(collection, field, value, limit=100, offset=0):
    if client:
        return list(
            client[settings.mongodb_database][collection]
            .find({field: value}, {"_id": 0})
            .sort("_id", 1)
            .skip(offset)
            .limit(limit)
        )
    with Session() as db:
        return [
            row.payload
            for row in db.scalars(
                select(LocalDocument)
                .where(
                    LocalDocument.collection == collection,
                    LocalDocument.payload[field].as_string() == value,
                )
                .order_by(LocalDocument.id)
                .offset(offset)
                .limit(limit)
            )
        ]
