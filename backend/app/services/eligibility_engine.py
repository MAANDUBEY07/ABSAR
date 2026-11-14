"""
Eligibility Engine Service for AVSAR
====================================
A rule-based, extensible eligibility evaluation engine designed to match
candidates (students, job seekers, citizens, artisans) with opportunities,
schemes, scholarships, grants, and jobs.

Features:
- Declarative criterion definitions supporting standard & composite logic.
- Rich operator support (numerical, categorical, range, set, pattern, regex).
- Nested profile attribute resolution via dot notation (e.g. "education.cgpa").
- Automatic age derivation from date of birth.
- Strict vs. preferential (mandatory vs. weighted) criteria evaluation.
- Detailed diagnostics: passed, failed, and missing profile attributes.
- Gap analysis and recommendations for ineligible candidates.
- Zero external dependencies (uses standard Python 3.8+).
"""

from __future__ import annotations

import copy
from datetime import date, datetime
from dataclasses import dataclass, field
from enum import Enum
import logging
import math
import re
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Operator(str, Enum):
    """Supported operators for criterion evaluation."""

    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    GREATER_THAN = "GREATER_THAN"
    GREATER_THAN_OR_EQUAL = "GREATER_THAN_OR_EQUAL"
    LESS_THAN = "LESS_THAN"
    LESS_THAN_OR_EQUAL = "LESS_THAN_OR_EQUAL"
    BETWEEN = "BETWEEN"  # Inclusive: [min, max]
    IN = "IN"  # Value in list/set
    NOT_IN = "NOT_IN"  # Value not in list/set
    CONTAINS = "CONTAINS"  # Candidate field (list/str) contains value
    NOT_CONTAINS = "NOT_CONTAINS"
    ANY_OF = "ANY_OF"  # Intersection between candidate list and allowed set
    ALL_OF = "ALL_OF"  # Candidate list contains all required values
    NONE_OF = "NONE_OF"  # Candidate list has no overlap with forbidden set
    EXISTS = "EXISTS"  # Field is present and not None
    NOT_EXISTS = "NOT_EXISTS"  # Field is absent or None
    REGEX_MATCH = "REGEX_MATCH"  # Regex matches string value
    CUSTOM = "CUSTOM"  # Custom evaluator function


class LogicalCombinator(str, Enum):
    """Combinators for rule groups."""

    AND = "AND"
    OR = "OR"
    NOT = "NOT"


class EligibilityStatus(str, Enum):
    """Overall outcome of an eligibility evaluation."""

    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    INCOMPLETE_DATA = "INCOMPLETE_DATA"  # Missing profile fields prevented a definitive pass
    # AVSAR API contract external statuses
    POTENTIALLY_ELIGIBLE = "POTENTIALLY_ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    CANNOT_DETERMINE = "CANNOT_DETERMINE"


class APIEligibilityStatus(str, Enum):
    """Externally visible AVSAR API contract eligibility statuses."""

    ELIGIBLE = "ELIGIBLE"
    POTENTIALLY_ELIGIBLE = "POTENTIALLY_ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    CANNOT_DETERMINE = "CANNOT_DETERMINE"


# ---------------------------------------------------------------------------
# Core Data Models
# ---------------------------------------------------------------------------


@dataclass
class Criterion:
    """
    Defines a single condition that a candidate profile must satisfy.

    Attributes:
        field: Name or dot-separated path to the profile field (e.g., 'age', 'education.percentage').
        operator: Comparison operator (Operator enum or matching string).
        value: Expected target, threshold, list, or range.
        description: Human-readable description of what this criterion checks.
        mandatory: If True, failure marks candidate as INELIGIBLE.
                   If False, failure only affects match score (preference rule).
        weight: Importance weight for scoring (default: 1.0).
        category: Logical grouping (e.g., 'Demographics', 'Education', 'Financial').
        custom_fn: Optional callable for CUSTOM operator: fn(candidate_value, expected_value) -> bool.
    """

    field: str
    operator: Union[Operator, str]
    value: Any = None
    description: Optional[str] = None
    mandatory: bool = True
    weight: float = 1.0
    category: Optional[str] = "General"
    custom_fn: Optional[Callable[[Any, Any], bool]] = None

    def __post_init__(self):
        if isinstance(self.operator, str):
            try:
                self.operator = Operator(self.operator.upper())
            except ValueError:
                # Custom operator name allowed
                pass

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "operator": self.operator.value
            if isinstance(self.operator, Operator)
            else str(self.operator),
            "value": self.value,
            "description": self.description or f"{self.field} {self.operator} {self.value}",
            "mandatory": self.mandatory,
            "weight": self.weight,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Criterion":
        return cls(
            field=data["field"],
            operator=data["operator"],
            value=data.get("value"),
            description=data.get("description"),
            mandatory=data.get("mandatory", True),
            weight=float(data.get("weight", 1.0)),
            category=data.get("category", "General"),
        )


@dataclass
class RuleGroup:
    """
    A composite logical group combining multiple Criteria or nested RuleGroups.
    """

    combinator: LogicalCombinator = LogicalCombinator.AND
    rules: List[Union[Criterion, "RuleGroup"]] = field(default_factory=list)
    description: Optional[str] = None
    mandatory: bool = True
    weight: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        serialized_rules = []
        for r in self.rules:
            if isinstance(r, (Criterion, RuleGroup)):
                serialized_rules.append(r.to_dict())
            elif isinstance(r, dict):
                serialized_rules.append(r)
        return {
            "combinator": self.combinator.value
            if isinstance(self.combinator, LogicalCombinator)
            else str(self.combinator),
            "rules": serialized_rules,
            "description": self.description,
            "mandatory": self.mandatory,
            "weight": self.weight,
        }


@dataclass
class CriterionResult:
    """Detailed result of evaluating a single Criterion."""

    criterion: Criterion
    passed: bool
    actual_value: Any
    expected_value: Any
    reason: str
    is_missing: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.criterion.field,
            "criterion_description": self.criterion.description
            or f"{self.criterion.field} {self.criterion.operator} {self.criterion.value}",
            "passed": self.passed,
            "actual_value": self.actual_value,
            "expected_value": self.expected_value,
            "mandatory": self.criterion.mandatory,
            "weight": self.criterion.weight,
            "category": self.criterion.category,
            "is_missing": self.is_missing,
            "reason": self.reason,
        }


@dataclass
class EligibilityResult:
    """
    Complete output of evaluating a candidate against an opportunity/scheme.
    """

    is_eligible: bool
    status: EligibilityStatus
    score: float  # Percentage score (0.0 to 100.0)
    passed_criteria: List[CriterionResult] = field(default_factory=list)
    failed_criteria: List[CriterionResult] = field(default_factory=list)
    missing_criteria: List[CriterionResult] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    scheme_id: Optional[str] = None
    scheme_title: Optional[str] = None

    @property
    def api_status(self) -> APIEligibilityStatus:
        """
        Maps internal engine status to the four required AVSAR API contract statuses:
        - ELIGIBLE -> ELIGIBLE
        - INELIGIBLE -> NOT_ELIGIBLE
        - INCOMPLETE_DATA -> POTENTIALLY_ELIGIBLE
        - CANNOT_DETERMINE -> CANNOT_DETERMINE
        """
        if self.status in (
            EligibilityStatus.CANNOT_DETERMINE,
            APIEligibilityStatus.CANNOT_DETERMINE,
        ):
            return APIEligibilityStatus.CANNOT_DETERMINE
        elif self.status in (
            EligibilityStatus.INCOMPLETE_DATA,
            APIEligibilityStatus.POTENTIALLY_ELIGIBLE,
        ):
            return APIEligibilityStatus.POTENTIALLY_ELIGIBLE
        elif self.status in (EligibilityStatus.INELIGIBLE, APIEligibilityStatus.NOT_ELIGIBLE):
            return APIEligibilityStatus.NOT_ELIGIBLE
        elif self.status in (EligibilityStatus.ELIGIBLE, APIEligibilityStatus.ELIGIBLE):
            return APIEligibilityStatus.ELIGIBLE
        return APIEligibilityStatus.NOT_ELIGIBLE

    @property
    def has_missing_student_info(self) -> bool:
        """Distinguishes missing student information from missing opportunity criteria."""
        return len(self.missing_fields) > 0

    @property
    def has_missing_opportunity_criteria(self) -> bool:
        """Indicates whether the opportunity itself lacks criteria specification."""
        return self.status in (
            EligibilityStatus.CANNOT_DETERMINE,
            APIEligibilityStatus.CANNOT_DETERMINE,
        )

    @property
    def summary(self) -> str:
        if self.status in (EligibilityStatus.ELIGIBLE, APIEligibilityStatus.ELIGIBLE):
            return f"Eligible with match score of {self.score:.1f}%."
        elif self.status in (
            EligibilityStatus.INCOMPLETE_DATA,
            APIEligibilityStatus.POTENTIALLY_ELIGIBLE,
        ):
            fields_str = ", ".join(self.missing_fields)
            return f"Incomplete Profile: Missing required fields ({fields_str}) to determine full eligibility."
        elif self.status in (
            EligibilityStatus.CANNOT_DETERMINE,
            APIEligibilityStatus.CANNOT_DETERMINE,
        ):
            return "Cannot Determine: Opportunity has no eligibility criteria defined."
        else:
            failed_mandatory = [c for c in self.failed_criteria if c.criterion.mandatory]
            reasons_str = (
                "; ".join([c.reason for c in failed_mandatory])
                or "Did not satisfy eligibility rules."
            )
            return f"Ineligible: {reasons_str}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scheme_id": self.scheme_id,
            "scheme_title": self.scheme_title,
            "is_eligible": self.is_eligible,
            "status": self.status.value,
            "api_status": self.api_status.value,
            "score": round(self.score, 2),
            "summary": self.summary,
            "reasons": self.reasons,
            "missing_fields": self.missing_fields,
            "has_missing_student_info": self.has_missing_student_info,
            "has_missing_opportunity_criteria": self.has_missing_opportunity_criteria,
            "passed_count": len(self.passed_criteria),
            "failed_count": len(self.failed_criteria),
            "missing_count": len(self.missing_criteria),
            "passed_criteria": [c.to_dict() for c in self.passed_criteria],
            "failed_criteria": [c.to_dict() for c in self.failed_criteria],
            "missing_criteria": [c.to_dict() for c in self.missing_criteria],
        }


@dataclass
class Scheme:
    """
    Represents an opportunity, welfare scheme, grant, or job opening in AVSAR.
    """

    id: str
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    criteria: List[Union[Criterion, RuleGroup, Dict[str, Any]]] = field(default_factory=list)
    min_score: float = 100.0  # Minimum score needed for optional/preference rules (0-100)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "criteria": [c.to_dict() if hasattr(c, "to_dict") else c for c in self.criteria],
            "min_score": self.min_score,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Scheme":
        parsed_criteria = []
        for item in data.get("criteria", []):
            if isinstance(item, (Criterion, RuleGroup)):
                parsed_criteria.append(item)
            elif isinstance(item, dict):
                if "combinator" in item:
                    parsed_criteria.append(cls._parse_rule_group(item))
                else:
                    parsed_criteria.append(Criterion.from_dict(item))
        return cls(
            id=str(data.get("id", "")),
            title=str(data.get("title", "")),
            description=data.get("description"),
            category=data.get("category"),
            criteria=parsed_criteria,
            min_score=float(data.get("min_score", 100.0)),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def _parse_rule_group(cls, data: Dict[str, Any]) -> RuleGroup:
        combinator = LogicalCombinator(data.get("combinator", "AND").upper())
        sub_rules = []
        for r in data.get("rules", []):
            if isinstance(r, dict):
                if "combinator" in r:
                    sub_rules.append(cls._parse_rule_group(r))
                else:
                    sub_rules.append(Criterion.from_dict(r))
            elif isinstance(r, (Criterion, RuleGroup)):
                sub_rules.append(r)
        return RuleGroup(
            combinator=combinator,
            rules=sub_rules,
            description=data.get("description"),
            mandatory=data.get("mandatory", True),
            weight=float(data.get("weight", 1.0)),
        )


@dataclass
class CandidateProfile:
    """
    Represents a candidate/user profile in AVSAR.
    Can be loaded directly from a dict or built incrementally.
    """

    id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    def get(self, key_path: str, default: Any = None) -> Any:
        return EligibilityEngine.resolve_field(self.data, key_path, default)

    def to_dict(self) -> Dict[str, Any]:
        result = copy.deepcopy(self.data)
        if self.id and "id" not in result:
            result["id"] = self.id
        return result

    @classmethod
    def from_dict(cls, profile_dict: Dict[str, Any]) -> "CandidateProfile":
        cand_id = (
            profile_dict.get("id")
            or profile_dict.get("candidate_id")
            or profile_dict.get("user_id")
        )
        return cls(id=str(cand_id) if cand_id else None, data=copy.deepcopy(profile_dict))


# ---------------------------------------------------------------------------
# Eligibility Engine Implementation
# ---------------------------------------------------------------------------


class EligibilityEngine:
    """
    Core Evaluation Engine for AVSAR.
    Evaluates candidate profiles against scheme criteria and outputs comprehensive verdicts.
    """

    def __init__(self):
        # Register standard operators to handler methods
        self._custom_operators: Dict[str, Callable[[Any, Any], bool]] = {}

    # -----------------------------------------------------------------------
    # Operator Registration
    # -----------------------------------------------------------------------

    def register_operator(self, name: str, handler: Callable[[Any, Any], bool]) -> None:
        """
        Register a custom operator dynamically.
        Handler signature: (candidate_value, expected_value) -> bool
        """
        self._custom_operators[name.upper()] = handler

    # -----------------------------------------------------------------------
    # Profile Attribute Resolution & Utilities
    # -----------------------------------------------------------------------

    @staticmethod
    def resolve_field(data: Any, path: str, default: Any = None) -> Any:
        """
        Resolves nested field paths using dot notation (e.g. 'education.cgpa', 'address.state').
        Supports list indexing like 'degrees.0.name'.
        Special handling: if path is 'age' and not explicitly in data, attempts to compute it from 'dob'.
        """
        if not data or not path:
            return default

        # Derived attribute: age from date_of_birth or dob
        if path == "age" and (isinstance(data, dict) and "age" not in data):
            dob_val = (
                data.get("dob")
                or data.get("date_of_birth")
                or data.get("birth_date")
                or data.get("personal", {}).get("dob")
            )
            if dob_val:
                computed_age = EligibilityEngine.calculate_age(dob_val)
                if computed_age is not None:
                    return computed_age

        tokens = path.split(".")
        current = data

        for token in tokens:
            if isinstance(current, dict):
                if token in current:
                    current = current[token]
                else:
                    return default
            elif isinstance(current, (list, tuple)):
                try:
                    idx = int(token)
                    if 0 <= idx < len(current):
                        current = current[idx]
                    else:
                        return default
                except ValueError:
                    # Projection: e.g. path 'skills.name' where skills is a list of dicts
                    projected = [
                        item.get(token)
                        for item in current
                        if isinstance(item, dict) and token in item
                    ]
                    current = projected if projected else default
            elif hasattr(current, token):
                current = getattr(current, token)
            else:
                return default

        return current

    @staticmethod
    def calculate_age(
        dob_input: Union[str, date, datetime], reference_date: Optional[date] = None
    ) -> Optional[int]:
        """Calculates current age in completed years from a date of birth."""
        if reference_date is None:
            reference_date = date.today()

        target_date: Optional[date] = None
        if isinstance(dob_input, datetime):
            target_date = dob_input.date()
        elif isinstance(dob_input, date):
            target_date = dob_input
        elif isinstance(dob_input, str):
            dob_str = dob_input.strip()
            # Try multiple common date formats
            formats = [
                "%Y-%m-%d",
                "%d-%m-%Y",
                "%d/%m/%Y",
                "%m/%d/%Y",
                "%Y/%m/%d",
                "%d.%m.%Y",
                "%Y.%m.%d",
            ]
            for fmt in formats:
                try:
                    target_date = datetime.strptime(dob_str, fmt).date()
                    break
                except ValueError:
                    continue

        if not target_date:
            return None

        # Age calculation
        years_diff = reference_date.year - target_date.year
        if (reference_date.month, reference_date.day) < (target_date.month, target_date.day):
            years_diff -= 1

        return max(0, years_diff)

    @staticmethod
    def _to_numeric(val: Any) -> Optional[float]:
        """Safely parses float or int from value."""
        if val is None or isinstance(val, bool):
            return None
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            val_clean = val.strip().replace(",", "")
            # Strip trailing '%' if present
            if val_clean.endswith("%"):
                val_clean = val_clean[:-1].strip()
            try:
                return float(val_clean)
            except ValueError:
                return None
        return None

    @staticmethod
    def _normalize_string(val: Any) -> str:
        """Converts value to a trimmed lowercase string for case-insensitive matching."""
        if val is None:
            return ""
        return str(val).strip().lower()

    # -----------------------------------------------------------------------
    # Evaluation of Single Criterion
    # -----------------------------------------------------------------------

    def evaluate_criterion(
        self, candidate_data: Dict[str, Any], criterion: Criterion
    ) -> CriterionResult:
        """
        Evaluates a candidate profile against a single Criterion.
        """
        actual_value = self.resolve_field(candidate_data, criterion.field, default=None)
        expected_value = criterion.value
        op = criterion.operator

        # Operator: EXISTS or NOT_EXISTS
        if op == Operator.EXISTS:
            passed = actual_value is not None and actual_value != ""
            reason = (
                f"Field '{criterion.field}' exists."
                if passed
                else f"Missing required field '{criterion.field}'."
            )
            return CriterionResult(
                criterion=criterion,
                passed=passed,
                actual_value=actual_value,
                expected_value="EXISTS",
                reason=reason,
                is_missing=(not passed),
            )

        if op == Operator.NOT_EXISTS:
            passed = actual_value is None or actual_value == ""
            reason = (
                f"Field '{criterion.field}' is absent as expected."
                if passed
                else f"Field '{criterion.field}' must not be present."
            )
            return CriterionResult(
                criterion=criterion,
                passed=passed,
                actual_value=actual_value,
                expected_value="NOT_EXISTS",
                reason=reason,
                is_missing=False,
            )

        # Check for missing field or unpopulated skills collection
        is_empty_skills = (
            isinstance(actual_value, (list, tuple, set))
            and len(actual_value) == 0
            and op in (Operator.CONTAINS, Operator.ANY_OF, Operator.ALL_OF)
            and "skill" in criterion.field.lower()
        )
        if actual_value is None or is_empty_skills:
            desc = criterion.description or f"Requirement on '{criterion.field}'"
            return CriterionResult(
                criterion=criterion,
                passed=False,
                actual_value=actual_value,
                expected_value=expected_value,
                reason=f"Candidate profile has no recorded '{criterion.field}' information ({desc}).",
                is_missing=True,
            )

        # Evaluate based on operator
        passed = False
        reason = ""

        try:
            # Custom function or registered operator
            if op == Operator.CUSTOM:
                if criterion.custom_fn:
                    passed = bool(criterion.custom_fn(actual_value, expected_value))
                else:
                    passed = False
                    reason = "CUSTOM operator specified but no custom_fn provided."

            elif isinstance(op, str) and op.upper() in self._custom_operators:
                handler = self._custom_operators[op.upper()]
                passed = bool(handler(actual_value, expected_value))

            # Numerical comparisons
            elif op in (
                Operator.GREATER_THAN,
                Operator.GREATER_THAN_OR_EQUAL,
                Operator.LESS_THAN,
                Operator.LESS_THAN_OR_EQUAL,
            ):
                cand_num = self._to_numeric(actual_value)
                exp_num = self._to_numeric(expected_value)

                if cand_num is None or exp_num is None:
                    # Fallback to direct comparison if types match (e.g. date strings)
                    try:
                        if op == Operator.GREATER_THAN:
                            passed = actual_value > expected_value
                        elif op == Operator.GREATER_THAN_OR_EQUAL:
                            passed = actual_value >= expected_value
                        elif op == Operator.LESS_THAN:
                            passed = actual_value < expected_value
                        elif op == Operator.LESS_THAN_OR_EQUAL:
                            passed = actual_value <= expected_value
                    except TypeError:
                        passed = False
                        reason = f"Cannot compare non-numeric or incompatible types: actual={actual_value}, expected={expected_value}."
                else:
                    if op == Operator.GREATER_THAN:
                        passed = cand_num > exp_num
                    elif op == Operator.GREATER_THAN_OR_EQUAL:
                        passed = cand_num >= exp_num
                    elif op == Operator.LESS_THAN:
                        passed = cand_num < exp_num
                    elif op == Operator.LESS_THAN_OR_EQUAL:
                        passed = cand_num <= exp_num

            # Range BETWEEN (inclusive)
            elif op == Operator.BETWEEN:
                cand_num = self._to_numeric(actual_value)
                if isinstance(expected_value, (list, tuple)) and len(expected_value) == 2:
                    min_val = self._to_numeric(expected_value[0])
                    max_val = self._to_numeric(expected_value[1])
                    if cand_num is not None and min_val is not None and max_val is not None:
                        passed = min_val <= cand_num <= max_val
                    else:
                        passed = False
                        reason = f"Invalid bounds for BETWEEN comparison: range={expected_value}, value={actual_value}."
                else:
                    passed = False
                    reason = (
                        f"BETWEEN operator expects [min, max] list or tuple, got {expected_value}."
                    )

            # Equality & Inequality
            elif op == Operator.EQUALS:
                # Case-insensitive if both are strings
                if isinstance(actual_value, str) and isinstance(expected_value, str):
                    passed = self._normalize_string(actual_value) == self._normalize_string(
                        expected_value
                    )
                else:
                    # Compare numeric if both can be numeric
                    n_act = self._to_numeric(actual_value)
                    n_exp = self._to_numeric(expected_value)
                    if n_act is not None and n_exp is not None:
                        passed = math.isclose(n_act, n_exp, rel_tol=1e-9)
                    else:
                        passed = actual_value == expected_value

            elif op == Operator.NOT_EQUALS:
                if isinstance(actual_value, str) and isinstance(expected_value, str):
                    passed = self._normalize_string(actual_value) != self._normalize_string(
                        expected_value
                    )
                else:
                    n_act = self._to_numeric(actual_value)
                    n_exp = self._to_numeric(expected_value)
                    if n_act is not None and n_exp is not None:
                        passed = not math.isclose(n_act, n_exp, rel_tol=1e-9)
                    else:
                        passed = actual_value != expected_value

            # Inclusion: IN & NOT_IN
            elif op in (Operator.IN, Operator.NOT_IN):
                exp_set = expected_value
                if not isinstance(exp_set, (list, tuple, set)):
                    exp_set = [exp_set]

                # Case-insensitive string matching when appropriate
                if isinstance(actual_value, str):
                    normalized_act = self._normalize_string(actual_value)
                    normalized_exp = {self._normalize_string(x) for x in exp_set}
                    is_member = normalized_act in normalized_exp
                else:
                    is_member = actual_value in exp_set

                passed = is_member if op == Operator.IN else (not is_member)

            # Container CONTAINS & NOT_CONTAINS
            elif op in (Operator.CONTAINS, Operator.NOT_CONTAINS):
                if isinstance(actual_value, (list, tuple, set)):
                    # Check membership
                    if isinstance(expected_value, str):
                        normalized_cand = {self._normalize_string(x) for x in actual_value}
                        contains = self._normalize_string(expected_value) in normalized_cand
                    else:
                        contains = expected_value in actual_value
                elif isinstance(actual_value, str):
                    # Substring check
                    contains = self._normalize_string(expected_value) in self._normalize_string(
                        actual_value
                    )
                else:
                    contains = False

                passed = contains if op == Operator.CONTAINS else (not contains)

            # Set operations: ANY_OF, ALL_OF, NONE_OF
            elif op in (Operator.ANY_OF, Operator.ALL_OF, Operator.NONE_OF):
                cand_list = (
                    actual_value if isinstance(actual_value, (list, tuple, set)) else [actual_value]
                )
                exp_list = (
                    expected_value
                    if isinstance(expected_value, (list, tuple, set))
                    else [expected_value]
                )

                # Normalize to strings if appropriate
                cand_norm = {self._normalize_string(x) for x in cand_list}
                exp_norm = {self._normalize_string(x) for x in exp_list}

                intersection = cand_norm.intersection(exp_norm)

                if op == Operator.ANY_OF:
                    passed = len(intersection) > 0
                elif op == Operator.ALL_OF:
                    passed = exp_norm.issubset(cand_norm)
                elif op == Operator.NONE_OF:
                    passed = len(intersection) == 0

            # Regex Match
            elif op == Operator.REGEX_MATCH:
                act_str = str(actual_value)
                pattern = str(expected_value)
                passed = bool(re.search(pattern, act_str, re.IGNORECASE))

            else:
                passed = False
                reason = f"Unknown or unsupported operator: {op}"

        except Exception as e:
            logger.exception("Error evaluating criterion %s: %s", criterion, e)
            passed = False
            reason = f"Evaluation error: {str(e)}"

        # Default diagnostic reason if not set
        if not reason:
            desc = criterion.description or f"{criterion.field} {op} {expected_value}"
            if passed:
                reason = f"Passed: {desc} (value was {actual_value})."
            else:
                reason = f"Failed: {desc} (actual value was {actual_value}, expected {op} {expected_value})."

        return CriterionResult(
            criterion=criterion,
            passed=passed,
            actual_value=actual_value,
            expected_value=expected_value,
            reason=reason,
            is_missing=False,
        )

    # -----------------------------------------------------------------------
    # Evaluation of Rule Groups (AND / OR / NOT)
    # -----------------------------------------------------------------------

    def evaluate_rule_group(
        self, candidate_data: Dict[str, Any], rule_group: RuleGroup
    ) -> Tuple[bool, List[CriterionResult]]:
        """
        Evaluates a composite RuleGroup containing AND, OR, or NOT logic.
        Returns: (passed: bool, list of sub-criterion results)
        """
        sub_results: List[CriterionResult] = []
        eval_outcomes: List[bool] = []

        for rule in rule_group.rules:
            if isinstance(rule, Criterion):
                c_res = self.evaluate_criterion(candidate_data, rule)
                sub_results.append(c_res)
                eval_outcomes.append(c_res.passed)
            elif isinstance(rule, RuleGroup):
                g_pass, g_sub = self.evaluate_rule_group(candidate_data, rule)
                sub_results.extend(g_sub)
                eval_outcomes.append(g_pass)
            elif isinstance(rule, dict):
                if "combinator" in rule:
                    parsed_grp = Scheme._parse_rule_group(rule)
                    g_pass, g_sub = self.evaluate_rule_group(candidate_data, parsed_grp)
                    sub_results.extend(g_sub)
                    eval_outcomes.append(g_pass)
                else:
                    c_obj = Criterion.from_dict(rule)
                    c_res = self.evaluate_criterion(candidate_data, c_obj)
                    sub_results.append(c_res)
                    eval_outcomes.append(c_res.passed)

        if not eval_outcomes:
            return True, sub_results

        combinator = rule_group.combinator
        if isinstance(combinator, str):
            combinator = LogicalCombinator(combinator.upper())

        if combinator == LogicalCombinator.AND:
            overall_pass = all(eval_outcomes)
        elif combinator == LogicalCombinator.OR:
            overall_pass = any(eval_outcomes)
        elif combinator == LogicalCombinator.NOT:
            # NOT inverts the first condition
            overall_pass = not eval_outcomes[0] if eval_outcomes else False
        else:
            overall_pass = all(eval_outcomes)

        return overall_pass, sub_results

    # -----------------------------------------------------------------------
    # Main Evaluation Interface
    # -----------------------------------------------------------------------

    def evaluate(
        self,
        candidate: Union[Dict[str, Any], CandidateProfile],
        scheme: Union[Dict[str, Any], Scheme],
    ) -> EligibilityResult:
        """
        Evaluates a candidate profile against a scheme/opportunity's eligibility rules.

        Returns an EligibilityResult with:
        - is_eligible: boolean
        - status: ELIGIBLE, INELIGIBLE, or INCOMPLETE_DATA
        - score: 0.0 to 100.0 compatibility score
        - detailed breakdown of passed, failed, and missing criteria
        """
        # Parse inputs if raw dicts
        cand_dict = (
            candidate.to_dict()
            if isinstance(candidate, CandidateProfile)
            else copy.deepcopy(candidate)
        )
        scheme_obj = Scheme.from_dict(scheme) if isinstance(scheme, dict) else scheme

        # Distinguish missing opportunity criteria: if scheme has no criteria defined
        if not scheme_obj.criteria:
            return EligibilityResult(
                is_eligible=False,
                status=EligibilityStatus.CANNOT_DETERMINE,
                score=0.0,
                passed_criteria=[],
                failed_criteria=[],
                missing_criteria=[],
                missing_fields=[],
                reasons=[
                    "Opportunity has no eligibility criteria defined; eligibility cannot be determined."
                ],
                scheme_id=scheme_obj.id,
                scheme_title=scheme_obj.title,
            )

        passed_criteria: List[CriterionResult] = []
        failed_criteria: List[CriterionResult] = []
        missing_criteria: List[CriterionResult] = []
        missing_fields: List[str] = []
        reasons: List[str] = []

        total_weight = 0.0
        earned_weight = 0.0
        has_mandatory_failure = False
        has_missing_mandatory = False

        for rule in scheme_obj.criteria:
            if isinstance(rule, Criterion):
                res = self.evaluate_criterion(cand_dict, rule)
                total_weight += rule.weight

                if res.is_missing:
                    missing_criteria.append(res)
                    if rule.field not in missing_fields:
                        missing_fields.append(rule.field)
                    if rule.mandatory:
                        has_missing_mandatory = True
                    reasons.append(res.reason)
                elif res.passed:
                    passed_criteria.append(res)
                    earned_weight += rule.weight
                else:
                    failed_criteria.append(res)
                    if rule.mandatory:
                        has_mandatory_failure = True
                    reasons.append(res.reason)

            elif isinstance(rule, RuleGroup):
                grp_pass, grp_results = self.evaluate_rule_group(cand_dict, rule)
                total_weight += rule.weight

                # Classify individual sub-results
                for sub in grp_results:
                    if sub.is_missing:
                        missing_criteria.append(sub)
                        if sub.criterion.field not in missing_fields:
                            missing_fields.append(sub.criterion.field)
                    elif sub.passed:
                        passed_criteria.append(sub)
                    else:
                        failed_criteria.append(sub)

                if grp_pass:
                    earned_weight += rule.weight
                else:
                    if rule.mandatory:
                        has_mandatory_failure = True
                    grp_desc = rule.description or f"Composite {rule.combinator} rule"
                    reasons.append(f"Failed rule group: {grp_desc}")

            elif isinstance(rule, dict):
                # Auto convert dict
                if "combinator" in rule:
                    grp = Scheme._parse_rule_group(rule)
                    grp_pass, grp_results = self.evaluate_rule_group(cand_dict, grp)
                    total_weight += grp.weight
                    for sub in grp_results:
                        if sub.is_missing:
                            missing_criteria.append(sub)
                            if sub.criterion.field not in missing_fields:
                                missing_fields.append(sub.criterion.field)
                        elif sub.passed:
                            passed_criteria.append(sub)
                        else:
                            failed_criteria.append(sub)
                    if grp_pass:
                        earned_weight += grp.weight
                    else:
                        if grp.mandatory:
                            has_mandatory_failure = True
                        reasons.append(f"Failed rule group: {grp.description or grp.combinator}")
                else:
                    crit = Criterion.from_dict(rule)
                    res = self.evaluate_criterion(cand_dict, crit)
                    total_weight += crit.weight
                    if res.is_missing:
                        missing_criteria.append(res)
                        if crit.field not in missing_fields:
                            missing_fields.append(crit.field)
                        if crit.mandatory:
                            has_missing_mandatory = True
                        reasons.append(res.reason)
                    elif res.passed:
                        passed_criteria.append(res)
                        earned_weight += crit.weight
                    else:
                        failed_criteria.append(res)
                        if crit.mandatory:
                            has_mandatory_failure = True
                        reasons.append(res.reason)

        # Calculate final percentage match score
        if total_weight > 0:
            score = (earned_weight / total_weight) * 100.0
        else:
            score = 100.0

        # Determine overall status
        if has_mandatory_failure:
            status = EligibilityStatus.INELIGIBLE
            is_eligible = False
        elif has_missing_mandatory:
            status = EligibilityStatus.INCOMPLETE_DATA
            is_eligible = False
        else:
            # All mandatory criteria passed or evaluated
            if score >= scheme_obj.min_score:
                status = EligibilityStatus.ELIGIBLE
                is_eligible = True
            else:
                status = EligibilityStatus.INELIGIBLE
                is_eligible = False
                reasons.append(
                    f"Match score ({score:.1f}%) is below minimum required score ({scheme_obj.min_score:.1f}%)."
                )

        return EligibilityResult(
            is_eligible=is_eligible,
            status=status,
            score=score,
            passed_criteria=passed_criteria,
            failed_criteria=failed_criteria,
            missing_criteria=missing_criteria,
            missing_fields=missing_fields,
            reasons=reasons,
            scheme_id=scheme_obj.id,
            scheme_title=scheme_obj.title,
        )

    # -----------------------------------------------------------------------
    # Batch & Recommendation Methods
    # -----------------------------------------------------------------------

    def filter_eligible_opportunities(
        self,
        candidate: Union[Dict[str, Any], CandidateProfile],
        opportunities: List[Union[Dict[str, Any], Scheme]],
        include_incomplete: bool = False,
    ) -> List[Tuple[Scheme, EligibilityResult]]:
        """
        Filters a list of schemes and returns eligible matches sorted by match score descending.
        Optionally includes schemes where candidate has INCOMPLETE_DATA.
        """
        results: List[Tuple[Scheme, EligibilityResult]] = []

        for opp in opportunities:
            opp_obj = Scheme.from_dict(opp) if isinstance(opp, dict) else opp
            eval_res = self.evaluate(candidate, opp_obj)

            if eval_res.is_eligible:
                results.append((opp_obj, eval_res))
            elif include_incomplete and eval_res.status == EligibilityStatus.INCOMPLETE_DATA:
                results.append((opp_obj, eval_res))

        # Sort by match score descending
        results.sort(key=lambda x: x[1].score, reverse=True)
        return results

    def get_gap_analysis(
        self,
        candidate: Union[Dict[str, Any], CandidateProfile],
        scheme: Union[Dict[str, Any], Scheme],
    ) -> Dict[str, Any]:
        """
        Generates an actionable gap analysis explaining what requirements
        the candidate meets, what is blocking them, and what profile fields
        need updating.
        """
        res = self.evaluate(candidate, scheme)
        scheme_obj = Scheme.from_dict(scheme) if isinstance(scheme, dict) else scheme

        actionable_steps: List[str] = []

        if res.missing_fields:
            actionable_steps.append(f"Update your profile with: {', '.join(res.missing_fields)}.")

        for failed in res.failed_criteria:
            if failed.criterion.mandatory:
                actionable_steps.append(
                    f"Mandatory requirement not met: {failed.criterion.description or failed.criterion.field}."
                )

        return {
            "scheme_id": scheme_obj.id,
            "scheme_title": scheme_obj.title,
            "status": res.status.value,
            "is_eligible": res.is_eligible,
            "score": round(res.score, 2),
            "summary": res.summary,
            "actionable_steps": actionable_steps,
            "passed_requirements": [
                p.criterion.description or p.criterion.field for p in res.passed_criteria
            ],
            "failed_requirements": [
                f.criterion.description or f.criterion.field for f in res.failed_criteria
            ],
            "missing_profile_fields": res.missing_fields,
        }

    # -----------------------------------------------------------------------
    # Common Preset Criterion Builders for AVSAR Schemes
    # -----------------------------------------------------------------------

    @staticmethod
    def build_age_criterion(
        min_age: Optional[int] = None, max_age: Optional[int] = None, mandatory: bool = True
    ) -> Criterion:
        """Helper to create age criteria."""
        if min_age is not None and max_age is not None:
            return Criterion(
                field="age",
                operator=Operator.BETWEEN,
                value=[min_age, max_age],
                description=f"Age must be between {min_age} and {max_age} years",
                mandatory=mandatory,
                category="Demographics",
            )
        elif min_age is not None:
            return Criterion(
                field="age",
                operator=Operator.GREATER_THAN_OR_EQUAL,
                value=min_age,
                description=f"Minimum age must be {min_age} years",
                mandatory=mandatory,
                category="Demographics",
            )
        elif max_age is not None:
            return Criterion(
                field="age",
                operator=Operator.LESS_THAN_OR_EQUAL,
                value=max_age,
                description=f"Maximum age must not exceed {max_age} years",
                mandatory=mandatory,
                category="Demographics",
            )
        raise ValueError("Must provide at least min_age or max_age.")

    @staticmethod
    def build_income_criterion(max_annual_income: float, mandatory: bool = True) -> Criterion:
        """Helper to create family annual income ceiling criteria."""
        return Criterion(
            field="annual_income",
            operator=Operator.LESS_THAN_OR_EQUAL,
            value=max_annual_income,
            description=f"Annual family income must not exceed INR {max_annual_income:,.0f}",
            mandatory=mandatory,
            category="Financial",
        )

    @staticmethod
    def build_caste_category_criterion(
        allowed_categories: List[str], mandatory: bool = True
    ) -> Criterion:
        """Helper to create caste/social category criteria (e.g. ['SC', 'ST', 'OBC', 'General', 'EWS'])."""
        return Criterion(
            field="category",
            operator=Operator.IN,
            value=allowed_categories,
            description=f"Category must be one of: {', '.join(allowed_categories)}",
            mandatory=mandatory,
            category="Demographics",
        )

    @staticmethod
    def build_gender_criterion(allowed_genders: List[str], mandatory: bool = True) -> Criterion:
        """Helper to create gender criteria (e.g. ['Female', 'Transgender'])."""
        return Criterion(
            field="gender",
            operator=Operator.IN,
            value=allowed_genders,
            description=f"Applicable for: {', '.join(allowed_genders)}",
            mandatory=mandatory,
            category="Demographics",
        )

    @staticmethod
    def build_domicile_criterion(allowed_states: List[str], mandatory: bool = True) -> Criterion:
        """Helper to create domicile/state residence criteria."""
        return Criterion(
            field="domicile_state",
            operator=Operator.IN,
            value=allowed_states,
            description=f"Candidate must be a resident of: {', '.join(allowed_states)}",
            mandatory=mandatory,
            category="Location",
        )

    @staticmethod
    def build_education_percentage_criterion(
        min_percentage: float, mandatory: bool = True
    ) -> Criterion:
        """Helper to create minimum marks percentage criteria."""
        return Criterion(
            field="education.percentage",
            operator=Operator.GREATER_THAN_OR_EQUAL,
            value=min_percentage,
            description=f"Minimum academic percentage required is {min_percentage}%",
            mandatory=mandatory,
            category="Education",
        )
