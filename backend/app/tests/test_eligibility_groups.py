import pytest
from app.services.eligibility_engine import Criterion, RuleGroup, Scheme, EligibilityEngine


@pytest.mark.parametrize(
    "value,expected", [(None, "INCOMPLETE_DATA"), (8, "INELIGIBLE"), (6, "ELIGIBLE")]
)
def test_missing_cgpa_under_not(value, expected):
    profile = {} if value is None else {"cgpa": value}
    rule = RuleGroup(combinator="NOT", rules=[Criterion("cgpa", "GREATER_THAN_OR_EQUAL", 7)])
    result = EligibilityEngine().evaluate(profile, Scheme("test", "Test", criteria=[rule]))
    assert result.status.value == expected
    if value is None:
        assert "cgpa" in result.missing_fields
        assert not result.is_eligible


@pytest.mark.parametrize(
    "combinator,known,expected",
    [("AND", True, None), ("AND", False, False), ("OR", True, True), ("OR", False, None)],
)
def test_three_state_groups(combinator, known, expected):
    rule = RuleGroup(
        combinator=combinator,
        rules=[
            Criterion("known", "EQUALS", True),
            RuleGroup(combinator="NOT", rules=[Criterion("cgpa", "GREATER_THAN_OR_EQUAL", 7)]),
        ],
    )
    outcome, results = EligibilityEngine().evaluate_rule_group({"known": known}, rule)
    assert outcome is expected
    assert any(result.is_missing for result in results)


def test_mixed_mandatory_unknown_and_known():
    rules = [
        Criterion("known", "EQUALS", True),
        RuleGroup(combinator="NOT", rules=[Criterion("cgpa", "GREATER_THAN_OR_EQUAL", 7)]),
    ]
    result = EligibilityEngine().evaluate({"known": True}, Scheme("test", "Test", criteria=rules))
    assert result.status.value == "INCOMPLETE_DATA"
    assert result.score == 50
