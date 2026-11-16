import pytest
from app.services import category_sources


@pytest.fixture
def listings(client, monkeypatch):
    rows = [
        dict(
            id="online",
            title="Python Contest",
            category="coding_competition",
            location="Bengaluru, Karnataka",
            remote=True,
        ),
        dict(
            id="offline",
            title="Python Workshop",
            category="coding_competition",
            location="Bengaluru, Karnataka",
            opportunity_mode="offline",
        ),
        dict(
            id="hybrid",
            title="Python Hybrid",
            category="coding_competition",
            location="Mumbai, Maharashtra",
            opportunity_mode="hybrid",
        ),
        dict(
            id="unknown",
            title="Python Unknown",
            category="coding_competition",
            location="Bengaluru",
            remote=False,
        ),
        dict(
            id="other",
            title="Python Job",
            category="job",
            location="Bengaluru",
            opportunity_mode="online",
        ),
    ]
    monkeypatch.setattr(category_sources, "listings", lambda category: rows)
    return client


def test_online_category_location_and_search_combine(listings, headers):
    response = listings.get(
        "/api/v1/opportunities",
        headers=headers(),
        params={
            "category": "coding_competition",
            "opportunity_mode": "online",
            "state": "  BENGALURU  ",
            "search": "python",
        },
    )
    assert response.status_code == 200
    assert [r["id"] for r in response.json()["data"]] == ["online"]


@pytest.mark.parametrize(
    "mode,expected", [("online", "online"), ("offline", "offline"), ("hybrid", "hybrid")]
)
def test_modes_are_distinct_and_unknown_is_not_offline(listings, headers, mode, expected):
    response = listings.get(
        "/api/v1/opportunities",
        headers=headers(),
        params={"category": "coding_competition", "opportunity_mode": mode},
    )
    assert [r["id"] for r in response.json()["data"]] == [expected]


def test_filters_are_applied_before_pagination(listings, headers):
    h = headers()
    params = {
        "category": "coding_competition",
        "search": "python",
        "state": "bengaluru",
        "limit": 1,
    }
    first = listings.get("/api/v1/opportunities", headers=h, params=params).json()["data"]
    second = listings.get("/api/v1/opportunities", headers=h, params=dict(params, offset=1)).json()[
        "data"
    ]
    assert [r["id"] for r in first] == ["online"]
    assert [r["id"] for r in second] == ["offline"]


def test_incompatible_combination_returns_empty(listings, headers):
    response = listings.get(
        "/api/v1/opportunities",
        headers=headers(),
        params={"category": "coding_competition", "opportunity_mode": "online", "state": "Mumbai"},
    )
    assert response.json()["data"] == []


def test_invalid_mode_is_rejected(listings, headers):
    assert (
        listings.get(
            "/api/v1/opportunities?opportunity_mode=invalid", headers=headers()
        ).status_code
        == 422
    )
