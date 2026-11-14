"""MongoDB hosted; durable SQL document table locally. No cross-store transaction."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.config.database import Session, mongo_client
from app.models.runtime import LocalDocument

COLLECTIONS = (
    "opportunities",
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
    return result


def scan(collection, limit=501, owner=None):
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
