import pytest

from app.services.location_filter import matches_location


@pytest.mark.parametrize(
    "location,query",
    [
        ("Bengaluru", "Karnataka"),
        ("Bengaluru, India", " Bangalore "),
        ("Bangalore", "bengaluru"),
        ("Gurgaon", "Haryana"),
        ("New Delhi", "Delhi"),
        ("Bhubaneswar", "Orissa"),
        ("Kolkata", "West Bengal"),
        ("Pune / Mumbai", "Maharashtra"),
        ("Berlin, Germany", "berlin"),
        ("  Bengaluru,   Karnataka  ", "bengaluru karnataka"),
    ],
)
def test_location_and_state_names(location, query):
    assert matches_location({"location": location}, query)


@pytest.mark.parametrize(
    "record,query",
    [
        ({"location": "Bangalore"}, "Goa"),
        ({"location": "New Delhi"}, "Haryana"),
        ({"location": "Pune"}, "Mumbai"),
        ({"location": "Online"}, "Karnataka"),
        ({"requirements": {"domicile_states": ["Bihar"]}}, "Bihar"),
        ({"description": "Office in Mumbai", "location": None}, "Maharashtra"),
    ],
)
def test_geography_does_not_match_unrelated_or_unknown_locations(record, query):
    assert not matches_location(record, query)


@pytest.mark.parametrize(
    "record",
    [
        {"state": "Karnataka"},
        {"city": "Bengaluru"},
        {"requirements": {"locations": ["Bangalore"]}},
        {"source_summary": {"locations": ["Bengaluru"]}},
    ],
)
def test_structured_geographic_fields(record):
    assert matches_location(record, "Karnataka")


def test_combined_state_city_and_mode_filter_before_pagination(client, headers, monkeypatch):
    rows = [
        {"id": "pune", "location": "Pune", "opportunity_mode": "offline"},
        {"id": "remote", "location": "Bengaluru", "opportunity_mode": "online"},
        {"id": "first", "location": "Bengaluru", "opportunity_mode": "offline"},
        {"id": "second", "location": "Bangalore", "opportunity_mode": "offline"},
    ]
    monkeypatch.setattr("app.services.arbeitnow.listings", lambda: rows)
    params = {
        "state": "Karnataka",
        "location": "Bangalore",
        "opportunity_mode": "offline",
        "limit": 1,
    }
    auth = headers()
    first = client.get("/api/v1/opportunities", headers=auth, params=params)
    assert first.status_code == 200
    assert [row["id"] for row in first.json()["data"]] == ["first"]
    second = client.get("/api/v1/opportunities", headers=auth, params=dict(params, offset=1))
    assert [row["id"] for row in second.json()["data"]] == ["second"]
    wrong_state = client.get(
        "/api/v1/opportunities", headers=auth, params=dict(params, state="Maharashtra")
    )
    assert wrong_state.json()["data"] == []


def test_legacy_state_accepts_city_and_empty_filters_are_ignored(client, headers, monkeypatch):
    monkeypatch.setattr(
        "app.services.arbeitnow.listings", lambda: [{"id": "city", "location": "Bengaluru"}]
    )
    response = client.get(
        "/api/v1/opportunities", headers=headers(), params={"state": "Bangalore", "location": "  "}
    )
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["data"]] == ["city"]
