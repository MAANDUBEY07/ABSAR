"""Profile integration against the fields already documented in the shared repository."""

from datetime import date, timedelta
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from app.config.database import Session
from app.models.profile import Education, Profile
from app.schemas.profile import ProfileInput
from app.services.eligibility_engine import EligibilityEngine, Scheme, Criterion, Operator


def test_legacy_eligibility_profile_persists_and_normalizes(client, headers):
    h = headers()
    body = dict(
        name="Student",
        dob="2004-01-10",
        gender="Female",
        category="SC",
        domicile_state="Bihar",
        domicile_district="Patna",
        annual_income=180000,
        differently_abled=True,
        disability_percentage=45,
        education={
            "highest_degree": "BTech",
            "percentage": 82,
            "passing_year": 2027,
            "institution": "Student supplied",
            "stream": "Computer Science",
        },
        skills=["Python"],
    )
    result = client.put("/api/v1/profile/me", headers=h, json=body)
    assert result.status_code == 200, result.text
    data = result.json()["data"]
    assert data["dob"] == data["date_of_birth"] == body["dob"]
    assert data["email"] == "student@example.test"
    assert data["id"]
    assert data["experience_months"] is None
    assert data["education"] == body["education"]
    assert client.get("/api/v1/profile", headers=h).json()["data"] == data
    with Session() as db:
        record = db.scalar(select(Education).where(Education.owner_id == data["id"]))
        assert record.payload["value"] == body["education"]
        profile = db.scalar(select(Profile).where(Profile.owner_id == data["id"]))
        assert profile.payload["annual_income"] == 180000
    criteria = [
        Criterion(field="age", operator=Operator.GREATER_THAN_OR_EQUAL, value=18),
        Criterion(field="annual_income", operator=Operator.LESS_THAN_OR_EQUAL, value=250000),
        Criterion(field="domicile_state", operator=Operator.EQUALS, value="Bihar"),
        Criterion(field="category", operator=Operator.IN, value=["SC", "ST"]),
        Criterion(field="education.percentage", operator=Operator.GREATER_THAN_OR_EQUAL, value=75),
    ]
    evaluation = EligibilityEngine().evaluate(
        data, Scheme(id="scholarship", title="Example", criteria=criteria)
    )
    assert evaluation.is_eligible


@pytest.mark.parametrize(
    "body",
    [
        {"annual_income": -1},
        {"disability_percentage": 101},
        {"disability_percentage": -1},
        {"dob": "2004-01-01", "date_of_birth": "2005-01-01"},
        {"dob": (date.today() + timedelta(days=1)).isoformat()},
    ],
)
def test_invalid_eligibility_profile_rejected(body):
    with pytest.raises(ValidationError):
        ProfileInput.model_validate(body)


def test_identity_fields_remain_read_only(client, headers):
    h = headers()
    for field in ["id", "owner_id", "email", "notification_email"]:
        result = client.put("/api/v1/profile", headers=h, json={field: "attacker@example.test"})
        assert result.status_code == 422
        assert "attacker@example.test" not in result.text


def test_education_list_and_missing_facts_remain_compatible(client, headers):
    h = headers()
    response = client.put("/api/v1/profile", headers=h, json={"education": [{"degree": "BTech"}]})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["annual_income"] is None
    assert response.json()["data"]["gender"] is None
    assert response.json()["data"]["education"] == [{"degree": "BTech"}]


def test_explicit_legacy_academics_reach_both_matching_interfaces(client, headers):
    h = headers()
    body = {
        "education": {
            "highest_degree": "BTech",
            "stream": "CS",
            "passing_year": 2027,
            "cgpa": 8.5,
            "percentage": 82,
        }
    }
    profile = client.put("/api/v1/profile", headers=h, json=body)
    assert profile.status_code == 200, profile.text
    oid = client.post(
        "/api/v1/opportunities",
        headers=h,
        json={
            "title": "Academic requirements",
            "requirements": {
                "confirmed": True,
                "degrees": ["BTech"],
                "branches": ["CS"],
                "graduation_years": [2027],
                "min_cgpa": 8,
            },
        },
    ).json()["data"]["id"]
    match = client.post("/api/v1/recommendations/match", headers=h, json={"opportunity_id": oid})
    assert match.json()["data"]["eligibility"] == "ELIGIBLE", match.text
    engine = client.post("/api/v1/eligibility/check/" + oid, headers=h)
    assert engine.json()["data"]["api_status"] == "ELIGIBLE", engine.text
    stored = client.get("/api/v1/profile", headers=h).json()["data"]
    assert stored["degree"] is None
    assert stored["education"] == body["education"]


def test_education_projection_does_not_invent_cgpa_or_select_an_arbitrary_degree():
    from app.integrations.profile import eligibility_profile

    assert eligibility_profile({"education": {"percentage": 90}}).get("cgpa") is None
    assert (
        eligibility_profile({"education": [{"degree": "BTech"}, {"degree": "MTech"}]}).get("degree")
        is None
    )
    assert (
        eligibility_profile({"degree": "MTech", "education": {"highest_degree": "BTech"}})["degree"]
        == "MTech"
    )
    assert eligibility_profile({"education": {"cgpa": "invalid"}}).get("cgpa") is None
