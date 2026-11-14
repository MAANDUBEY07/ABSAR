"""
Duplicate Detector Service
==========================
Reusable duplicate detection service for AVSAR opportunities using:
- Deterministic SHA-256 exact content hashing.
- RapidFuzz token-based and fuzzy ratio matching.
- Multi-field weighted scoring (title, organization, description, deadline).
- Conflict detection and safety guards (differing organizations, conflicting deadlines).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple

from rapidfuzz import fuzz


# ---------------------------------------------------------------------------
# Configuration & Result Models
# ---------------------------------------------------------------------------

@dataclass
class DuplicateDetectorConfig:
    """Configurable thresholds and field weights for duplicate opportunity detection."""

    # Matching thresholds (0.0 to 1.0)
    duplicate_threshold: float = 0.80
    suspected_threshold: float = 0.60
    min_org_similarity: float = 0.45
    min_title_similarity_guard: float = 0.55

    # Penalties
    deadline_conflict_penalty: float = 0.20

    # Field weights (sum = 1.0)
    title_weight: float = 0.50
    organization_weight: float = 0.25
    description_weight: float = 0.15
    deadline_weight: float = 0.10

    def __post_init__(self) -> None:
        """Validates configuration thresholds, weights, and penalties."""
        thresholds = {
            "duplicate_threshold": self.duplicate_threshold,
            "suspected_threshold": self.suspected_threshold,
            "min_org_similarity": self.min_org_similarity,
            "min_title_similarity_guard": self.min_title_similarity_guard,
        }
        for name, value in thresholds.items():
            if not isinstance(value, (int, float)) or not (0.0 <= value <= 1.0):
                raise ValueError(
                    f"Invalid {name}: must be a float between 0.0 and 1.0, got {value}"
                )

        if not isinstance(self.deadline_conflict_penalty, (int, float)) or not (
            0.0 <= self.deadline_conflict_penalty <= 1.0
        ):
            raise ValueError(
                f"Invalid deadline_conflict_penalty: must be between 0.0 and 1.0, got {self.deadline_conflict_penalty}"
            )

        weights = {
            "title_weight": self.title_weight,
            "organization_weight": self.organization_weight,
            "description_weight": self.description_weight,
            "deadline_weight": self.deadline_weight,
        }
        for name, weight in weights.items():
            if not isinstance(weight, (int, float)) or weight < 0.0:
                raise ValueError(
                    f"Invalid {name}: weight must be non-negative, got {weight}"
                )

        total_weight = sum(weights.values())
        if abs(total_weight - 1.0) > 1e-5:
            raise ValueError(
                f"Field weights must sum to 1.0, got {total_weight:.4f} (weights: {weights})"
            )


@dataclass
class DuplicateComparisonResult:
    """Detailed verdict of comparing two opportunities for duplicate status."""

    is_duplicate: bool
    is_exact_match: bool
    confidence_score: float
    field_scores: Dict[str, float]
    explanation: str
    reasons: List[str]
    requires_review: bool = False
    deadline_conflict: bool = False
    candidate_id: Optional[str] = None
    existing_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize comparison result to a standard dictionary."""
        return {
            "is_duplicate": self.is_duplicate,
            "is_exact_match": self.is_exact_match,
            "confidence_score": round(self.confidence_score, 4),
            "field_scores": {k: round(v, 4) for k, v in self.field_scores.items()},
            "explanation": self.explanation,
            "reasons": self.reasons,
            "requires_review": self.requires_review,
            "deadline_conflict": self.deadline_conflict,
            "candidate_id": self.candidate_id,
            "existing_id": self.existing_id,
        }


# ---------------------------------------------------------------------------
# Text & Date Normalization Utilities
# ---------------------------------------------------------------------------

def normalize_text(text: Any) -> str:
    """
    Normalizes a text string by stripping, converting to lowercase,
    removing punctuation noise, and collapsing multiple spaces.
    """
    if text is None:
        return ""
    text_str = str(text).strip().lower()
    if not text_str:
        return ""
    # Replace non-alphanumeric characters with spaces
    text_str = re.sub(r"[^\w\s]", " ", text_str)
    # Collapse multiple whitespace characters into a single space
    text_str = re.sub(r"\s+", " ", text_str).strip()
    return text_str


def normalize_deadline(deadline: Any) -> Optional[date]:
    """
    Parses various date/deadline string formats or datetime objects
    into a standardized datetime.date object.

    Indian Date Format Convention:
    The application primarily targets Indian opportunities. In India, dates are
    predominantly written in Day-Month-Year (DD/MM/YYYY) format.
    For ambiguous slash-separated dates (e.g. '05/06/2026'), DD/MM/YYYY is the
    preferred and canonical interpretation (i.e. 5 June 2026, NOT 6 May 2026).
    Therefore, '%d/%m/%Y' and '%d-%m-%Y' are strictly evaluated before any
    US-style '%m/%d/%Y' fallbacks.
    """
    if not deadline:
        return None
    if isinstance(deadline, datetime):
        return deadline.date()
    if isinstance(deadline, date):
        return deadline

    deadline_str = str(deadline).strip()
    if not deadline_str:
        return None

    # Handle ISO formats like 2026-12-30T23:59:59.000Z
    iso_clean = deadline_str.split("T")[0]

    # Note: DD/MM/YYYY is strictly placed before MM/DD/YYYY for Indian date preference
    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",  # Preferred Indian convention (e.g., 05/06/2026 -> 5th June 2026)
        "%m/%d/%Y",  # Fallback for dates where month > 12 fails in %d/%m/%Y
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%Y/%m/%d",
        "%d.%m.%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(iso_clean, fmt).date()
        except ValueError:
            pass
        try:
            return datetime.strptime(deadline_str, fmt).date()
        except ValueError:
            pass

    return None


def compare_deadlines(d1_val: Any, d2_val: Any) -> Tuple[Optional[float], bool, str]:
    """
    Compares two deadline values.
    Returns: (score: Optional[float], is_conflict: bool, reason: str)
    """
    if not d1_val or not d2_val:
        return None, False, "Deadline omitted in one or both opportunities"

    norm1 = normalize_deadline(d1_val)
    norm2 = normalize_deadline(d2_val)

    if norm1 and norm2:
        days_diff = abs((norm1 - norm2).days)
        if days_diff == 0:
            return 1.0, False, f"Deadlines are identical ({norm1})"
        elif days_diff <= 2:
            return 0.9, False, f"Deadlines are very close ({days_diff} days apart: {norm1} vs {norm2})"
        elif days_diff <= 7:
            return 0.7, False, f"Deadlines are within one week ({days_diff} days apart: {norm1} vs {norm2})"
        else:
            return 0.0, True, f"Deadlines conflict ({norm1} vs {norm2}, difference of {days_diff} days)"

    # Fallback to normalized text comparison for non-standard date strings
    text1 = normalize_text(d1_val)
    text2 = normalize_text(d2_val)
    if text1 and text2:
        if text1 == text2:
            return 1.0, False, f"Deadline text matches ('{d1_val}')"
        sim = fuzz.token_sort_ratio(text1, text2) / 100.0
        if sim >= 0.85:
            return sim, False, f"Deadline text is highly similar ('{d1_val}' vs '{d2_val}')"
        return 0.0, True, f"Deadline strings differ significantly ('{d1_val}' vs '{d2_val}')"

    return None, False, "Deadline could not be parsed"


# ---------------------------------------------------------------------------
# Core Duplicate Detection Functions
# ---------------------------------------------------------------------------

def generate_content_hash(opportunity: Dict[str, Any]) -> str:
    """
    Generates a deterministic SHA-256 hash of normalized core opportunity attributes.
    Attributes hashed: title, organization/provider, normalized deadline, category.
    """
    if not opportunity:
        return ""

    title = normalize_text(opportunity.get("title"))
    org = normalize_text(opportunity.get("organization") or opportunity.get("provider"))
    dl_date = normalize_deadline(opportunity.get("deadline"))
    dl_str = dl_date.isoformat() if dl_date else normalize_text(opportunity.get("deadline"))
    category = normalize_text(opportunity.get("category"))

    if not title and not org:
        return ""

    canonical = f"title:{title}|org:{org}|deadline:{dl_str}|category:{category}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compare_opportunities(
    opp1: Dict[str, Any],
    opp2: Dict[str, Any],
    config: Optional[DuplicateDetectorConfig] = None,
) -> DuplicateComparisonResult:
    """
    Compares two opportunity dictionaries and returns a structured verdict.
    """
    cfg = config or DuplicateDetectorConfig()

    cand_id = str(opp1.get("id") or opp1.get("_id") or "") or None
    exist_id = str(opp2.get("id") or opp2.get("_id") or "") or None

    t1 = normalize_text(opp1.get("title"))
    t2 = normalize_text(opp2.get("title"))
    o1 = normalize_text(opp1.get("organization") or opp1.get("provider"))
    o2 = normalize_text(opp2.get("organization") or opp2.get("provider"))
    d1 = normalize_text(opp1.get("description"))
    d2 = normalize_text(opp2.get("description"))
    dl1 = opp1.get("deadline")
    dl2 = opp2.get("deadline")

    # Require both titles: reject comparison if either opportunity has a missing or empty title
    if not opp1 or not opp2 or not t1 or not t2:
        reasons: List[str] = []
        if not opp1 or not opp2:
            reasons.append("One or both opportunities have empty data.")
        if not t1 and not t2:
            reasons.append("Both opportunities have missing or empty titles.")
        elif not t1:
            reasons.append("First opportunity has missing or empty title.")
        elif not t2:
            reasons.append("Second opportunity has missing or empty title.")

        return DuplicateComparisonResult(
            is_duplicate=False,
            is_exact_match=False,
            confidence_score=0.0,
            field_scores={},
            explanation="Insufficient opportunity data for comparison: both opportunities must have a valid title.",
            reasons=reasons,
            candidate_id=cand_id,
            existing_id=exist_id,
        )

    # Exact content hash comparison
    hash1 = generate_content_hash(opp1)
    hash2 = generate_content_hash(opp2)
    if hash1 and hash2 and hash1 == hash2:
        exact_scores: Dict[str, float] = {"title": 1.0}
        if o1 or o2:
            exact_scores["organization"] = 1.0
        if d1 or d2:
            exact_scores["description"] = 1.0
        if dl1 or dl2:
            exact_scores["deadline"] = 1.0

        return DuplicateComparisonResult(
            is_duplicate=True,
            is_exact_match=True,
            confidence_score=1.0,
            field_scores=exact_scores,
            explanation="Exact duplicate detected (identical SHA-256 content hash).",
            reasons=["Normalized content hashes match exactly."],
            requires_review=False,
            deadline_conflict=False,
            candidate_id=cand_id,
            existing_id=exist_id,
        )

    # Fuzzy field similarity calculations
    field_scores: Dict[str, float] = {}
    reasons: List[str] = []

    # 1. Title Similarity (fuzz.token_sort_ratio handles word reordering and typos)
    if t1 and t2:
        title_sim = max(fuzz.token_sort_ratio(t1, t2), fuzz.ratio(t1, t2)) / 100.0
    else:
        title_sim = 0.0
    field_scores["title"] = title_sim
    reasons.append(f"Title similarity: {title_sim:.1%}")

    # 2. Organization Similarity (token_set_ratio handles 'Google' vs 'Google India')
    org_sim: Optional[float] = None
    if o1 and o2:
        org_sim = max(fuzz.token_sort_ratio(o1, o2), fuzz.token_set_ratio(o1, o2)) / 100.0
        field_scores["organization"] = org_sim
        reasons.append(f"Organization similarity: {org_sim:.1%}")
    else:
        reasons.append("Organization omitted in one or both opportunities")

    # 3. Description Similarity
    desc_sim: Optional[float] = None
    if d1 and d2:
        desc_sim = max(fuzz.token_set_ratio(d1, d2), fuzz.token_sort_ratio(d1, d2)) / 100.0
        field_scores["description"] = desc_sim
        reasons.append(f"Description similarity: {desc_sim:.1%}")
    else:
        reasons.append("Description omitted in one or both opportunities")

    # 4. Deadline Comparison
    deadline_sim, is_deadline_conflict, dl_reason = compare_deadlines(dl1, dl2)
    if deadline_sim is not None:
        field_scores["deadline"] = deadline_sim
        reasons.append(f"Deadline evaluation: {dl_reason}")
    else:
        reasons.append(f"Deadline evaluation: {dl_reason}")

    # Weighted scoring with dynamic re-weighting for available fields
    total_weight = cfg.title_weight
    earned_weight = title_sim * cfg.title_weight

    if org_sim is not None:
        total_weight += cfg.organization_weight
        earned_weight += org_sim * cfg.organization_weight

    if desc_sim is not None:
        total_weight += cfg.description_weight
        earned_weight += desc_sim * cfg.description_weight

    if deadline_sim is not None:
        total_weight += cfg.deadline_weight
        earned_weight += deadline_sim * cfg.deadline_weight

    raw_score = (earned_weight / total_weight) if total_weight > 0 else 0.0

    # Deadline Conflict Guard: Reduce confidence and flag for review if deadlines conflict
    requires_review = False
    if is_deadline_conflict:
        penalized_score = max(0.0, raw_score - cfg.deadline_conflict_penalty)
        requires_review = True
        reasons.append(
            f"Deadline conflict detected. Confidence penalized by {cfg.deadline_conflict_penalty:.0%} "
            f"({raw_score:.1%} -> {penalized_score:.1%}). Flagged for review."
        )
        score_after_penalties = penalized_score
    else:
        score_after_penalties = raw_score

    # Safety Guard 1: Do not classify opportunities as duplicates based on title similarity alone
    if o1 and o2 and org_sim is not None:
        if org_sim < cfg.min_org_similarity:
            # When organizations differ, scale down duplicate confidence proportionally
            org_ratio = max(0.0, org_sim / cfg.min_org_similarity)
            adjusted_score = min(score_after_penalties * org_ratio, 0.29)
            reasons.append(
                f"Different organizations ('{opp1.get('organization') or o1}' vs "
                f"'{opp2.get('organization') or o2}') prevent duplicate classification."
            )
            return DuplicateComparisonResult(
                is_duplicate=False,
                is_exact_match=False,
                confidence_score=adjusted_score,
                field_scores=field_scores,
                explanation="Not a duplicate: organizations differ significantly despite title similarity.",
                reasons=reasons,
                requires_review=False,
                deadline_conflict=is_deadline_conflict,
                candidate_id=cand_id,
                existing_id=exist_id,
            )

    # Safety Guard 2: Title alone with no corroborating organization or attributes
    if org_sim is None and desc_sim is None and deadline_sim is None:
        # Only title could be compared
        if title_sim >= cfg.duplicate_threshold:
            return DuplicateComparisonResult(
                is_duplicate=False,
                is_exact_match=False,
                confidence_score=title_sim * 0.70,  # Discounted confidence
                field_scores=field_scores,
                explanation="Suspected duplicate based on title, but requires review due to missing organization and details.",
                reasons=reasons + ["Title similarity alone is insufficient for automatic duplicate confirmation."],
                requires_review=True,
                deadline_conflict=False,
                candidate_id=cand_id,
                existing_id=exist_id,
            )

    confidence_score = score_after_penalties

    # Final Classification
    if confidence_score >= cfg.duplicate_threshold:
        is_duplicate = True
        explanation = f"Duplicate opportunity detected (confidence: {confidence_score:.1%})."
    elif confidence_score >= cfg.suspected_threshold:
        is_duplicate = False
        requires_review = True
        explanation = f"Potential duplicate detected requiring review (confidence: {confidence_score:.1%})."
    else:
        is_duplicate = False
        explanation = f"Distinct opportunity (confidence: {confidence_score:.1%})."

    return DuplicateComparisonResult(
        is_duplicate=is_duplicate,
        is_exact_match=False,
        confidence_score=confidence_score,
        field_scores=field_scores,
        explanation=explanation,
        reasons=reasons,
        requires_review=requires_review,
        deadline_conflict=is_deadline_conflict,
        candidate_id=cand_id,
        existing_id=exist_id,
    )


def find_duplicates(
    new_opp: Dict[str, Any],
    existing_opps: List[Dict[str, Any]],
    config: Optional[DuplicateDetectorConfig] = None,
    threshold: Optional[float] = None,
) -> List[DuplicateComparisonResult]:
    """
    Checks a new opportunity against a collection of existing opportunities,
    returning all matches that meet or exceed the duplicate or suspected threshold,
    sorted by confidence score descending.
    """
    cfg = config or DuplicateDetectorConfig()
    cutoff = threshold if threshold is not None else cfg.suspected_threshold

    matches: List[DuplicateComparisonResult] = []
    for existing in existing_opps:
        result = compare_opportunities(new_opp, existing, cfg)
        if result.is_duplicate or result.confidence_score >= cutoff:
            matches.append(result)

    # Sort descending by confidence score, putting exact matches first
    matches.sort(key=lambda m: (m.is_exact_match, m.confidence_score), reverse=True)
    return matches


# ---------------------------------------------------------------------------
# Reusable Service Class
# ---------------------------------------------------------------------------

class DuplicateDetector:
    """Service class encapsulating duplicate detection with configured settings."""

    def __init__(self, config: Optional[DuplicateDetectorConfig] = None):
        self.config = config or DuplicateDetectorConfig()

    def generate_hash(self, opportunity: Dict[str, Any]) -> str:
        """Generates content hash for an opportunity."""
        return generate_content_hash(opportunity)

    def compare(self, opp1: Dict[str, Any], opp2: Dict[str, Any]) -> DuplicateComparisonResult:
        """Compares two opportunities."""
        return compare_opportunities(opp1, opp2, self.config)

    def find_duplicates(
        self,
        new_opp: Dict[str, Any],
        existing_opps: List[Dict[str, Any]],
        threshold: Optional[float] = None,
    ) -> List[DuplicateComparisonResult]:
        """Finds all potential duplicates for an opportunity within a collection."""
        return find_duplicates(new_opp, existing_opps, self.config, threshold=threshold)
