"""Bounded public RSS discovery; not a general multi-site scraper."""

from app.models.base import now
from app.services.catalog import digest


def discover_feed(feed_url, owner):
    args = {"feed_url": feed_url}
    from defusedxml import ElementTree
    from app.services.safe_fetch import fetch
    from app.services.catalog import create_opportunity
    from app.repositories import documents

    root = ElementTree.fromstring(fetch(args["feed_url"]))
    results = []
    for item in root.findall(".//item")[:50]:
        title, link = item.findtext("title"), item.findtext("link")
        if title:
            from app.schemas.persistent import OpportunityInput

            data = OpportunityInput(
                title=title[:300],
                description=(item.findtext("description") or "")[:30000],
                application_url=link or None,
                source_url=args["feed_url"],
            ).model_dump(mode="json")
            raw_id = digest([args["feed_url"], title, link])[:32]
            documents.put(
                "raw_listings",
                raw_id,
                dict(owner_id=owner, source_url=args["feed_url"], title=title, link=link),
                insert_only=True,
            )
            results.append(create_opportunity(data)["id"])
    record = dict(
        owner_id=owner,
        opportunity_ids=results,
        connector="PUBLIC_RSS",
        completed_at=now().isoformat(),
    )
    documents.put("discovery_jobs", digest([owner, args])[:32], record)
    return record
