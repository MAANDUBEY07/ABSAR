"""All project-owner categories persist without changing existing identifiers or envelopes."""

import pytest
from app.schemas.opportunity import CANONICAL_CATEGORIES, CATEGORY_LABELS, OpportunityInput
from app.repositories import documents


def test_exact_canonical_vocabulary():
    assert CANONICAL_CATEGORIES == (
        "scholarship",
        "internship",
        "job",
        "government_scheme",
        "fellowship",
        "apprenticeship",
        "hackathon",
        "coding_competition",
        "innovation_challenge",
        "startup_challenge",
        "grant",
    )


@pytest.mark.parametrize("category", CANONICAL_CATEGORIES)
def test_categories_and_metadata_round_trip(client, headers, category):
    h = headers()
    body = dict(
        title="Example " + category,
        category=category,
        opportunity_mode="online",
        category_metadata={"source_supplied": {"tags": ["student"], "note": None}},
    )
    result = client.post("/api/v1/opportunities", headers=h, json=body)
    assert result.status_code == 201, result.text
    assert set(result.json()) == {"data", "meta"}
    data = result.json()["data"]
    assert data["category"] == category
    assert data["opportunity_mode"] == "online"
    assert data["category_metadata"] == body["category_metadata"]
    assert (
        documents.get("opportunities", data["id"])["category_metadata"] == body["category_metadata"]
    )
    assert client.get("/api/v1/opportunities/" + data["id"], headers=h).json()["data"] == data
    page = client.get("/api/v1/opportunities", headers=h, params={"category": category}).json()
    assert page["data"][0]["id"] == data["id"]


@pytest.mark.parametrize("label,canonical", CATEGORY_LABELS.items())
def test_supplied_labels_normalize_to_existing_api_identifiers(label, canonical):
    assert OpportunityInput(title="Example", category=label).category == canonical


@pytest.mark.parametrize("category", ["scheme", "competition", "other"])
def test_legacy_values_remain_accepted(category):
    value = OpportunityInput(title="Old listing", category=category)
    assert value.category == category
    assert value.opportunity_mode is None
    assert value.category_metadata == {}


def test_unsupported_category_is_not_silently_reclassified(client, headers):
    result = client.post(
        "/api/v1/opportunities",
        headers=headers(),
        json={"title": "Unknown", "category": "unagreed_new_category"},
    )
    assert result.status_code == 422


@pytest.mark.parametrize("mode", ["online", "offline", "hybrid"])
def test_stage1_modes(mode):
    assert OpportunityInput(title="Example", opportunity_mode=mode).opportunity_mode == mode


def test_stage1_invalid_mode():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        OpportunityInput(title="Example", opportunity_mode="unknown")
