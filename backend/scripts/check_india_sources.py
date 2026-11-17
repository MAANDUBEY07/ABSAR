"""Explicit, read-only live source smoke check; never called by CI."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        required=True,
        help="Allow requests to the registered public sources",
    )
    parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.schemas.opportunity import CANONICAL_CATEGORIES
    from app.services.india_sources import listings, source_status

    rows = listings()
    counts = Counter(row["category"] for row in rows)
    print(
        json.dumps(
            {
                "total": len(rows),
                "categories": {category: counts[category] for category in CANONICAL_CATEGORIES},
                "sources": source_status(),
            },
            indent=2,
        )
    )
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
