"""
Unit tests for AVSAR Eligibility Engine
=======================================
Covers:
- Standard comparison operators (numerical, categorical, range, set, regex, custom)
- Nested dot-notation attribute resolution and list indexing
- Automatic age calculation from date of birth
- Mandatory vs. preference/optional rules and score calculation
- Missing profile data detection and INCOMPLETE_DATA status
- Composite boolean rule groups (AND, OR, NOT)
- Batch opportunity filtering and sorting
- Gap analysis and actionable recommendations
- Scheme and Criterion dictionary serialization/deserialization
"""

import json
import os
import sys
import unittest
from datetime import date, timedelta

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.services.eligibility_engine import (
    APIEligibilityStatus,
    CandidateProfile,
    Criterion,
    CriterionResult,
    EligibilityEngine,
    EligibilityResult,
    EligibilityStatus,
    LogicalCombinator,
    Operator,
    RuleGroup,
    Scheme,
)


class TestEligibilityEngineBasicOperators(unittest.TestCase):
    def setUp(self):
        self.engine = EligibilityEngine()

    def test_equals_and_not_equals_numeric(self):
        crit_eq = Criterion(field="marks", operator=Operator.EQUALS, value=85)
        crit_neq = Criterion(field="marks", operator=Operator.NOT_EQUALS, value=90)

        res1 = self.engine.evaluate_criterion({"marks": 85}, crit_eq)
        self.assertTrue(res1.passed)

        res2 = self.engine.evaluate_criterion({"marks": "85.0"}, crit_eq)
        self.assertTrue(res2.passed)

        res3 = self.engine.evaluate_criterion({"marks": 80}, crit_eq)
        self.assertFalse(res3.passed)

        res4 = self.engine.evaluate_criterion({"marks": 90}, crit_neq)
        self.assertFalse(res4.passed)

        res5 = self.engine.evaluate_criterion({"marks": 85}, crit_neq)
        self.assertTrue(res5.passed)

    def test_string_case_insensitivity(self):
        crit = Criterion(field="category", operator=Operator.EQUALS, value="General")
        res1 = self.engine.evaluate_criterion({"category": "general"}, crit)
        self.assertTrue(res1.passed)

        res2 = self.engine.evaluate_criterion({"category": " GENERAL "}, crit)
        self.assertTrue(res2.passed)

        res3 = self.engine.evaluate_criterion({"category": "OBC"}, crit)
        self.assertFalse(res3.passed)

    def test_numerical_comparisons(self):
        gt_crit = Criterion(field="score", operator=Operator.GREATER_THAN, value=50)
        gte_crit = Criterion(field="score", operator=Operator.GREATER_THAN_OR_EQUAL, value=50)
        lt_crit = Criterion(field="age", operator=Operator.LESS_THAN, value=30)
        lte_crit = Criterion(field="age", operator=Operator.LESS_THAN_OR_EQUAL, value=30)

        self.assertTrue(self.engine.evaluate_criterion({"score": 51}, gt_crit).passed)
        self.assertFalse(self.engine.evaluate_criterion({"score": 50}, gt_crit).passed)

        self.assertTrue(self.engine.evaluate_criterion({"score": 50}, gte_crit).passed)
        self.assertTrue(self.engine.evaluate_criterion({"score": "65%"}, gte_crit).passed)

        self.assertTrue(self.engine.evaluate_criterion({"age": 29}, lt_crit).passed)
        self.assertFalse(self.engine.evaluate_criterion({"age": 30}, lt_crit).passed)

        self.assertTrue(self.engine.evaluate_criterion({"age": 30}, lte_crit).passed)
        self.assertFalse(self.engine.evaluate_criterion({"age": 31}, lte_crit).passed)

    def test_between_operator(self):
        between_crit = Criterion(field="age", operator=Operator.BETWEEN, value=[18, 25])

        self.assertTrue(self.engine.evaluate_criterion({"age": 18}, between_crit).passed)
        self.assertTrue(self.engine.evaluate_criterion({"age": 21}, between_crit).passed)
        self.assertTrue(self.engine.evaluate_criterion({"age": 25}, between_crit).passed)
        self.assertFalse(self.engine.evaluate_criterion({"age": 17}, between_crit).passed)
        self.assertFalse(self.engine.evaluate_criterion({"age": 26}, between_crit).passed)

    def test_in_and_not_in(self):
        crit_in = Criterion(field="state", operator=Operator.IN, value=["Bihar", "Uttar Pradesh", "Jharkhand"])
        crit_not_in = Criterion(field="state", operator=Operator.NOT_IN, value=["Delhi", "Goa"])

        self.assertTrue(self.engine.evaluate_criterion({"state": "bihar"}, crit_in).passed)
        self.assertTrue(self.engine.evaluate_criterion({"state": "Uttar Pradesh"}, crit_in).passed)
        self.assertFalse(self.engine.evaluate_criterion({"state": "Maharashtra"}, crit_in).passed)

        self.assertTrue(self.engine.evaluate_criterion({"state": "Bihar"}, crit_not_in).passed)
        self.assertFalse(self.engine.evaluate_criterion({"state": "delhi"}, crit_not_in).passed)

    def test_contains_and_not_contains(self):
        crit_contains_str = Criterion(field="degree", operator=Operator.CONTAINS, value="Engineering")
        crit_contains_list = Criterion(field="skills", operator=Operator.CONTAINS, value="Python")

        self.assertTrue(self.engine.evaluate_criterion({"degree": "Bachelor of Engineering (B.E.)"}, crit_contains_str).passed)
        self.assertFalse(self.engine.evaluate_criterion({"degree": "Bachelor of Arts"}, crit_contains_str).passed)

        self.assertTrue(self.engine.evaluate_criterion({"skills": ["Java", "python", "SQL"]}, crit_contains_list).passed)
        self.assertFalse(self.engine.evaluate_criterion({"skills": ["Java", "C++"]}, crit_contains_list).passed)

    def test_set_operations_any_all_none(self):
        crit_any = Criterion(field="skills", operator=Operator.ANY_OF, value=["Python", "Go", "Rust"])
        crit_all = Criterion(field="qualifications", operator=Operator.ALL_OF, value=["10th", "12th"])
        crit_none = Criterion(field="criminal_records", operator=Operator.NONE_OF, value=["convicted", "pending"])

        self.assertTrue(self.engine.evaluate_criterion({"skills": ["Python", "JavaScript"]}, crit_any).passed)
        self.assertFalse(self.engine.evaluate_criterion({"skills": ["Java", "PHP"]}, crit_any).passed)

        self.assertTrue(self.engine.evaluate_criterion({"qualifications": ["10th", "12th", "B.Tech"]}, crit_all).passed)
        self.assertFalse(self.engine.evaluate_criterion({"qualifications": ["10th"]}, crit_all).passed)

        self.assertTrue(self.engine.evaluate_criterion({"criminal_records": ["cleared"]}, crit_none).passed)
        self.assertFalse(self.engine.evaluate_criterion({"criminal_records": ["convicted"]}, crit_none).passed)

    def test_exists_and_not_exists(self):
        crit_exists = Criterion(field="income_certificate", operator=Operator.EXISTS)
        crit_not_exists = Criterion(field="disqualification_flag", operator=Operator.NOT_EXISTS)

        self.assertTrue(self.engine.evaluate_criterion({"income_certificate": "DOC1234"}, crit_exists).passed)
        self.assertFalse(self.engine.evaluate_criterion({"income_certificate": None}, crit_exists).passed)
        self.assertFalse(self.engine.evaluate_criterion({}, crit_exists).passed)

        self.assertTrue(self.engine.evaluate_criterion({}, crit_not_exists).passed)
        self.assertFalse(self.engine.evaluate_criterion({"disqualification_flag": True}, crit_not_exists).passed)

    def test_regex_match(self):
        crit = Criterion(field="pan_number", operator=Operator.REGEX_MATCH, value=r"^[A-Z]{5}[0-9]{4}[A-Z]$")

        self.assertTrue(self.engine.evaluate_criterion({"pan_number": "ABCDE1234F"}, crit).passed)
        self.assertFalse(self.engine.evaluate_criterion({"pan_number": "INVALID123"}, crit).passed)

    def test_custom_operator_and_function(self):
        # Register a custom operator: DIVISIBLE_BY
        self.engine.register_operator("DIVISIBLE_BY", lambda act, exp: act % exp == 0)
        crit_custom_op = Criterion(field="roll_number", operator="DIVISIBLE_BY", value=5)

        self.assertTrue(self.engine.evaluate_criterion({"roll_number": 25}, crit_custom_op).passed)
        self.assertFalse(self.engine.evaluate_criterion({"roll_number": 23}, crit_custom_op).passed)

        # Custom function on criterion directly
        crit_fn = Criterion(
            field="word",
            operator=Operator.CUSTOM,
            custom_fn=lambda act, exp: len(act) > exp,
            value=4
        )
        self.assertTrue(self.engine.evaluate_criterion({"word": "opportunity"}, crit_fn).passed)
        self.assertFalse(self.engine.evaluate_criterion({"word": "job"}, crit_fn).passed)


class TestNestedFieldResolutionAndAge(unittest.TestCase):
    def setUp(self):
        self.engine = EligibilityEngine()

    def test_nested_dot_notation(self):
        candidate = {
            "personal": {
                "demographics": {
                    "gender": "Female",
                    "caste": "OBC"
                }
            },
            "education": {
                "secondary": {
                    "marks": 92.5
                }
            },
            "skills": [
                {"name": "Python", "level": "Expert"},
                {"name": "Django", "level": "Intermediate"}
            ]
        }

        crit1 = Criterion(field="personal.demographics.gender", operator=Operator.EQUALS, value="Female")
        self.assertTrue(self.engine.evaluate_criterion(candidate, crit1).passed)

        crit2 = Criterion(field="education.secondary.marks", operator=Operator.GREATER_THAN_OR_EQUAL, value=90)
        self.assertTrue(self.engine.evaluate_criterion(candidate, crit2).passed)

        # List indexing
        crit3 = Criterion(field="skills.0.name", operator=Operator.EQUALS, value="Python")
        self.assertTrue(self.engine.evaluate_criterion(candidate, crit3).passed)

    def test_age_calculation_from_dob(self):
        today = date.today()
        twenty_years_ago = today - timedelta(days=20 * 365 + 5)
        dob_str = twenty_years_ago.strftime("%Y-%m-%d")

        candidate = {
            "name": "Aman",
            "dob": dob_str
        }

        # Age criterion should automatically resolve age from dob
        age_crit = Criterion(field="age", operator=Operator.GREATER_THAN_OR_EQUAL, value=18)
        res = self.engine.evaluate_criterion(candidate, age_crit)
        self.assertTrue(res.passed)
        self.assertGreaterEqual(res.actual_value, 20)

    def test_calculate_age_edge_cases(self):
        ref_date = date(2026, 6, 1)

        # Born exactly 20 years before reference date
        age1 = EligibilityEngine.calculate_age("2006-06-01", reference_date=ref_date)
        self.assertEqual(age1, 20)

        # Birthday hasn't happened yet this year
        age2 = EligibilityEngine.calculate_age("2006-08-15", reference_date=ref_date)
        self.assertEqual(age2, 19)

        # Birthday passed earlier this year
        age3 = EligibilityEngine.calculate_age("2006-01-10", reference_date=ref_date)
        self.assertEqual(age3, 20)

        # Format variations
        age_slash = EligibilityEngine.calculate_age("01/06/2006", reference_date=ref_date)
        self.assertEqual(age_slash, 20)


class TestFullSchemeEvaluation(unittest.TestCase):
    def setUp(self):
        self.engine = EligibilityEngine()

        # Define a sample government scholarship scheme for higher education
        self.scholarship_scheme = Scheme(
            id="SCHOLARSHIP_001",
            title="Post-Matric Merit Scholarship for Youth",
            description="Financial support for low-income students in higher technical education.",
            criteria=[
                EligibilityEngine.build_age_criterion(min_age=17, max_age=25, mandatory=True),
                EligibilityEngine.build_income_criterion(max_annual_income=250000, mandatory=True),
                EligibilityEngine.build_caste_category_criterion(["SC", "ST", "OBC", "EWS"], mandatory=True),
                Criterion(field="education.percentage", operator=Operator.GREATER_THAN_OR_EQUAL, value=60.0, mandatory=True, description="Min 60% marks"),
                # Optional preference: Female candidates get preference/bonus score
                Criterion(field="gender", operator=Operator.EQUALS, value="Female", mandatory=False, weight=2.0, description="Preference for female candidates"),
            ],
            min_score=80.0
        )

    def test_fully_eligible_candidate(self):
        candidate = {
            "name": "Priya Sharma",
            "age": 20,
            "annual_income": 180000,
            "category": "OBC",
            "education": {"percentage": 78.5},
            "gender": "Female"
        }

        result = self.engine.evaluate(candidate, self.scholarship_scheme)
        self.assertTrue(result.is_eligible)
        self.assertEqual(result.status, EligibilityStatus.ELIGIBLE)
        self.assertEqual(result.score, 100.0)
        self.assertEqual(len(result.passed_criteria), 5)
        self.assertEqual(len(result.failed_criteria), 0)

    def test_eligible_without_optional_preference(self):
        candidate = {
            "name": "Rahul Verma",
            "age": 21,
            "annual_income": 150000,
            "category": "SC",
            "education": {"percentage": 65.0},
            "gender": "Male"  # Fails optional female preference (weight 2.0)
        }

        # 4 mandatory criteria with weight 1.0 each = 4.0; optional female preference weight 2.0. Total = 6.0
        # Earned = 4.0 -> score = 66.67%
        # Scheme has min_score=80.0, so score check fails
        result = self.engine.evaluate(candidate, self.scholarship_scheme)
        self.assertFalse(result.is_eligible)
        self.assertEqual(result.status, EligibilityStatus.INELIGIBLE)

        # If scheme min_score is lower (e.g. 60.0), Rahul is eligible!
        self.scholarship_scheme.min_score = 60.0
        result2 = self.engine.evaluate(candidate, self.scholarship_scheme)
        self.assertTrue(result2.is_eligible)
        self.assertEqual(result2.status, EligibilityStatus.ELIGIBLE)

    def test_ineligible_due_to_income_and_age(self):
        candidate = {
            "name": "Vikram",
            "age": 28,  # Too old (> 25)
            "annual_income": 500000,  # Income exceeds 2.5 LPA
            "category": "SC",
            "education": {"percentage": 75.0},
            "gender": "Male"
        }

        result = self.engine.evaluate(candidate, self.scholarship_scheme)
        self.assertFalse(result.is_eligible)
        self.assertEqual(result.status, EligibilityStatus.INELIGIBLE)
        self.assertEqual(len(result.failed_criteria), 3)  # Age, Income, Gender preference
        failed_fields = [f.criterion.field for f in result.failed_criteria]
        self.assertIn("age", failed_fields)
        self.assertIn("annual_income", failed_fields)

    def test_incomplete_profile_missing_fields(self):
        # Candidate has not provided income and education details
        candidate = {
            "name": "Sneha",
            "age": 19,
            "category": "ST",
            "gender": "Female"
        }

        result = self.engine.evaluate(candidate, self.scholarship_scheme)
        self.assertFalse(result.is_eligible)
        self.assertEqual(result.status, EligibilityStatus.INCOMPLETE_DATA)
        self.assertIn("annual_income", result.missing_fields)
        self.assertIn("education.percentage", result.missing_fields)
        self.assertTrue("Incomplete Profile" in result.summary)


class TestCompositeRuleGroups(unittest.TestCase):
    def setUp(self):
        self.engine = EligibilityEngine()

    def test_or_rule_group(self):
        # Candidate is eligible if:
        # (State == "Bihar" AND Category in ["SC", "ST"]) OR (Annual Income <= 100,000)
        bihar_affirmative = RuleGroup(
            combinator=LogicalCombinator.AND,
            rules=[
                Criterion(field="domicile_state", operator=Operator.EQUALS, value="Bihar"),
                Criterion(field="category", operator=Operator.IN, value=["SC", "ST"])
            ],
            description="Bihar SC/ST affirmative quota"
        )
        low_income_rule = Criterion(
            field="annual_income",
            operator=Operator.LESS_THAN_OR_EQUAL,
            value=100000,
            description="BPL income threshold"
        )

        composite_rule = RuleGroup(
            combinator=LogicalCombinator.OR,
            rules=[bihar_affirmative, low_income_rule],
            description="Eligible via quota OR income threshold"
        )

        scheme = Scheme(
            id="SCHEME_OR_01",
            title="State Welfare Grant",
            criteria=[composite_rule]
        )

        # Candidate 1: Qualifies via Bihar + SC (even though income is high)
        cand1 = {"domicile_state": "Bihar", "category": "SC", "annual_income": 400000}
        res1 = self.engine.evaluate(cand1, scheme)
        self.assertTrue(res1.is_eligible)

        # Candidate 2: Qualifies via low income (even though state is Delhi and General)
        cand2 = {"domicile_state": "Delhi", "category": "General", "annual_income": 80000}
        res2 = self.engine.evaluate(cand2, scheme)
        self.assertTrue(res2.is_eligible)

        # Candidate 3: Ineligible on both branches
        cand3 = {"domicile_state": "Delhi", "category": "General", "annual_income": 250000}
        res3 = self.engine.evaluate(cand3, scheme)
        self.assertFalse(res3.is_eligible)

    def test_not_rule_group(self):
        # NOT rule: Candidate must NOT be an existing government employee
        not_gov_employee = RuleGroup(
            combinator=LogicalCombinator.NOT,
            rules=[
                Criterion(field="employment_type", operator=Operator.EQUALS, value="Government")
            ],
            description="Must not be currently employed in government service"
        )

        scheme = Scheme(id="SCHEME_NOT_01", title="Youth Training", criteria=[not_gov_employee])

        self.assertTrue(self.engine.evaluate({"employment_type": "Private"}, scheme).is_eligible)
        self.assertTrue(self.engine.evaluate({"employment_type": "Unemployed"}, scheme).is_eligible)
        self.assertFalse(self.engine.evaluate({"employment_type": "Government"}, scheme).is_eligible)


class TestBatchFilteringAndGapAnalysis(unittest.TestCase):
    def setUp(self):
        self.engine = EligibilityEngine()

        self.scheme1 = Scheme(
            id="S1",
            title="Artisan Support Scheme",
            criteria=[
                Criterion(field="occupation", operator=Operator.EQUALS, value="Artisan"),
                Criterion(field="annual_income", operator=Operator.LESS_THAN_OR_EQUAL, value=200000)
            ],
            min_score=100.0
        )
        self.scheme2 = Scheme(
            id="S2",
            title="Women Entrepreneurship Loan",
            criteria=[
                Criterion(field="gender", operator=Operator.EQUALS, value="Female"),
                Criterion(field="age", operator=Operator.BETWEEN, value=[21, 50]),
                Criterion(field="business_registered", operator=Operator.EQUALS, value=True, mandatory=False, weight=1.0)
            ],
            min_score=66.0
        )
        self.scheme3 = Scheme(
            id="S3",
            title="Graduate IT Fellowship",
            criteria=[
                Criterion(field="education.degree", operator=Operator.IN, value=["B.Tech", "B.E.", "MCA"]),
                Criterion(field="skills", operator=Operator.CONTAINS, value="Python")
            ],
            min_score=100.0
        )

    def test_filter_eligible_opportunities(self):
        candidate = {
            "name": "Kavita",
            "gender": "Female",
            "age": 28,
            "occupation": "Artisan",
            "annual_income": 150000,
            "education": {"degree": "B.A."},
            "business_registered": False
        }

        eligible_schemes = self.engine.filter_eligible_opportunities(
            candidate, [self.scheme1, self.scheme2, self.scheme3]
        )

        # Kavita is eligible for Artisan Scheme (100%) and Women Entrepreneurship Loan (>66%)
        # But not IT fellowship (degree mismatch)
        self.assertEqual(len(eligible_schemes), 2)
        matched_ids = [s[0].id for s in eligible_schemes]
        self.assertIn("S1", matched_ids)
        self.assertIn("S2", matched_ids)
        self.assertNotIn("S3", matched_ids)

        # S1 should have higher score than S2
        self.assertGreaterEqual(eligible_schemes[0][1].score, eligible_schemes[1][1].score)

    def test_gap_analysis(self):
        candidate = {
            "gender": "Male",
            "age": 30
            # Missing business_registered
        }

        gap = self.engine.get_gap_analysis(candidate, self.scheme2)
        self.assertFalse(gap["is_eligible"])
        self.assertEqual(gap["status"], "INELIGIBLE")
        self.assertTrue(len(gap["actionable_steps"]) > 0)
        self.assertIn("gender", gap["failed_requirements"][0].lower())


class TestSerializationAndBuilders(unittest.TestCase):
    def test_criterion_and_scheme_serialization(self):
        c = Criterion(field="age", operator=Operator.BETWEEN, value=[18, 30], mandatory=True, weight=2.5)
        c_dict = c.to_dict()
        c_restored = Criterion.from_dict(c_dict)
        self.assertEqual(c.field, c_restored.field)
        self.assertEqual(c.operator, c_restored.operator)
        self.assertEqual(c.value, c_restored.value)
        self.assertEqual(c.weight, c_restored.weight)

        scheme = Scheme(
            id="SCH_TEST",
            title="Test Scheme",
            criteria=[c],
            min_score=90.0,
            metadata={"department": "Ministry of Skill Development"}
        )
        s_dict = scheme.to_dict()
        s_restored = Scheme.from_dict(s_dict)
        self.assertEqual(scheme.id, s_restored.id)
        self.assertEqual(scheme.title, s_restored.title)
        self.assertEqual(scheme.min_score, s_restored.min_score)
        self.assertEqual(len(scheme.criteria), len(s_restored.criteria))

    def test_preset_builders(self):
        age_c = EligibilityEngine.build_age_criterion(min_age=18, max_age=35)
        self.assertEqual(age_c.operator, Operator.BETWEEN)
        self.assertEqual(age_c.value, [18, 35])

        income_c = EligibilityEngine.build_income_criterion(300000)
        self.assertEqual(income_c.operator, Operator.LESS_THAN_OR_EQUAL)
        self.assertEqual(income_c.value, 300000)

        domicile_c = EligibilityEngine.build_domicile_criterion(["Bihar", "Odisha"])
        self.assertEqual(domicile_c.operator, Operator.IN)
        self.assertEqual(domicile_c.value, ["Bihar", "Odisha"])


class TestFourStatusMapping(unittest.TestCase):
    """
    Tests specifically covering the four externally visible AVSAR API contract statuses:
    - ELIGIBLE
    - NOT_ELIGIBLE
    - POTENTIALLY_ELIGIBLE
    - CANNOT_DETERMINE
    """

    def setUp(self):
        self.engine = EligibilityEngine()

    def test_status_eligible(self):
        scheme = Scheme(
            id="SCH_ELIGIBLE",
            title="Eligible Test Scheme",
            criteria=[
                Criterion(field="age", operator=Operator.GREATER_THAN_OR_EQUAL, value=18, mandatory=True),
                Criterion(field="domicile_state", operator=Operator.EQUALS, value="Bihar", mandatory=True),
            ],
            min_score=100.0,
        )
        candidate = {"age": 22, "domicile_state": "Bihar"}

        res = self.engine.evaluate(candidate, scheme)
        self.assertTrue(res.is_eligible)
        self.assertEqual(res.status, EligibilityStatus.ELIGIBLE)
        self.assertEqual(res.api_status, APIEligibilityStatus.ELIGIBLE)
        self.assertEqual(res.api_status.value, "ELIGIBLE")
        self.assertFalse(res.has_missing_student_info)
        self.assertFalse(res.has_missing_opportunity_criteria)

    def test_status_not_eligible(self):
        scheme = Scheme(
            id="SCH_NOT_ELIGIBLE",
            title="Age Gated Scheme",
            criteria=[
                Criterion(field="age", operator=Operator.LESS_THAN_OR_EQUAL, value=25, mandatory=True),
            ],
        )
        candidate = {"age": 30}  # Over max age

        res = self.engine.evaluate(candidate, scheme)
        self.assertFalse(res.is_eligible)
        self.assertEqual(res.status, EligibilityStatus.INELIGIBLE)
        self.assertEqual(res.api_status, APIEligibilityStatus.NOT_ELIGIBLE)
        self.assertEqual(res.api_status.value, "NOT_ELIGIBLE")

    def test_status_potentially_eligible_missing_mandatory_skill(self):
        # Mandatory skill requirement
        scheme = Scheme(
            id="SCH_SKILL",
            title="Python Developer Fellowship",
            criteria=[
                Criterion(field="skills", operator=Operator.CONTAINS, value="Python", mandatory=True),
                Criterion(field="age", operator=Operator.GREATER_THAN_OR_EQUAL, value=18, mandatory=True),
            ],
        )
        # Student profile satisfies age, but has no skills listed
        candidate = {"age": 20}

        res = self.engine.evaluate(candidate, scheme)
        # Must NOT be rejected as NOT_ELIGIBLE; must be POTENTIALLY_ELIGIBLE
        self.assertFalse(res.is_eligible)
        self.assertEqual(res.status, EligibilityStatus.INCOMPLETE_DATA)
        self.assertEqual(res.api_status, APIEligibilityStatus.POTENTIALLY_ELIGIBLE)
        self.assertEqual(res.api_status.value, "POTENTIALLY_ELIGIBLE")
        self.assertTrue(res.has_missing_student_info)
        self.assertIn("skills", res.missing_fields)
        self.assertIn("Incomplete Profile: Missing required fields (skills)", res.summary)
        self.assertIn("Candidate profile has no recorded 'skills' information", res.reasons[0])

    def test_status_cannot_determine_empty_criteria(self):
        # Opportunity has no criteria defined
        empty_scheme = Scheme(
            id="SCH_EMPTY",
            title="Unconfigured Opportunity",
            criteria=[],
        )
        candidate = {"name": "Maan", "age": 21}

        res = self.engine.evaluate(candidate, empty_scheme)
        self.assertFalse(res.is_eligible)
        self.assertEqual(res.status, EligibilityStatus.CANNOT_DETERMINE)
        self.assertEqual(res.api_status, APIEligibilityStatus.CANNOT_DETERMINE)
        self.assertEqual(res.api_status.value, "CANNOT_DETERMINE")
        self.assertTrue(res.has_missing_opportunity_criteria)
        self.assertFalse(res.has_missing_student_info)

    def test_api_contract_json_serialization(self):
        scheme = Scheme(
            id="SCH_JSON",
            title="JSON Contract Scheme",
            criteria=[
                Criterion(field="age", operator=Operator.BETWEEN, value=[18, 30], mandatory=True),
            ],
        )
        candidate = {"age": 24}

        res = self.engine.evaluate(candidate, scheme)
        data = res.to_dict()

        # Verify JSON serializability
        json_str = json.dumps(data)
        parsed = json.loads(json_str)

        # Verify required API contract fields
        self.assertIn("scheme_id", parsed)
        self.assertIn("status", parsed)
        self.assertIn("api_status", parsed)
        self.assertIn("is_eligible", parsed)
        self.assertIn("score", parsed)
        self.assertIn("summary", parsed)
        self.assertIn("reasons", parsed)
        self.assertIn("missing_fields", parsed)
        self.assertIn("has_missing_student_info", parsed)
        self.assertIn("has_missing_opportunity_criteria", parsed)
        self.assertIn("passed_criteria", parsed)
        self.assertIn("failed_criteria", parsed)
        self.assertIn("missing_criteria", parsed)
        self.assertEqual(parsed["api_status"], "ELIGIBLE")


if __name__ == "__main__":
    unittest.main()
