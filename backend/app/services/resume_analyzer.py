"""
AVSAR Resume Analyzer & Skill Extraction Service
=================================================
Parses uploaded resumes (PDF or raw text), extracts candidate skills, education,
and estimated years of experience, and computes readiness scores against opportunities.
Conforms strictly to the AVSAR ResumeAnalysisResponse API contract.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from io import BytesIO
from typing import Any

from app.integrations.resume_claims import claims as claims

import pymupdf

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Standard Skill Taxonomy & Canonical Mappings
# ---------------------------------------------------------------------------

SKILL_TAXONOMY: dict[str, list[str]] = {
    # Programming Languages
    "python": ["python", "python3", "py"],
    "javascript": ["javascript", "js", "ecmascript"],
    "typescript": ["typescript", "ts"],
    "java": ["java", "core java", "j2ee"],
    "c++": ["c++", "cpp"],
    "c#": ["c#", "csharp", "c-sharp"],
    "c": ["c programming", "embedded c"],
    "go": ["golang", "go language"],
    "rust": ["rust", "rustlang"],
    "kotlin": ["kotlin"],
    "swift": ["swift", "swiftui"],
    "sql": ["sql", "mysql", "postgresql", "sqlite", "tsql", "plsql"],
    "html": ["html", "html5"],
    "css": ["css", "css3", "sass", "tailwind", "bootstrap"],
    "php": ["php"],
    "ruby": ["ruby", "ruby on rails"],
    "r": ["r programming", "r language"],
    # Frameworks & Libraries
    "react": ["react", "react.js", "reactjs", "react native"],
    "node.js": ["node", "node.js", "nodejs"],
    "next.js": ["next.js", "nextjs"],
    "fastapi": ["fastapi", "fast-api"],
    "django": ["django", "django rest framework", "drf"],
    "flask": ["flask"],
    "express": ["express", "express.js", "expressjs"],
    "spring boot": ["spring boot", "springboot", "spring framework"],
    "angular": ["angular", "angularjs"],
    "vue.js": ["vue", "vue.js", "vuejs"],
    "tailwind css": ["tailwind", "tailwind css", "tailwindcss"],
    "redux": ["redux", "redux toolkit"],
    # AI, ML & Data Science
    "machine learning": ["machine learning", "ml", "pattern recognition"],
    "deep learning": ["deep learning", "dl", "neural networks"],
    "pytorch": ["pytorch"],
    "tensorflow": ["tensorflow", "tf", "keras"],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "scikit-learn": ["scikit-learn", "sklearn"],
    "nlp": ["nlp", "natural language processing", "spacy", "nltk", "transformers"],
    "computer vision": ["computer vision", "opencv"],
    "generative ai": ["generative ai", "genai", "llm", "large language models"],
    "langchain": ["langchain", "llamaindex", "rag"],
    "huggingface": ["huggingface", "hugging face"],
    # Cloud & DevOps
    "docker": ["docker", "containerization"],
    "kubernetes": ["kubernetes", "k8s"],
    "aws": ["aws", "amazon web services", "ec2", "s3", "lambda"],
    "azure": ["azure", "microsoft azure"],
    "gcp": ["gcp", "google cloud", "google cloud platform"],
    "terraform": ["terraform"],
    "ansible": ["ansible"],
    "git": ["git", "github", "gitlab", "version control"],
    "ci/cd": ["ci/cd", "continuous integration", "github actions", "jenkins"],
    "linux": ["linux", "ubuntu", "bash", "shell scripting"],
    # Databases, Storage & Messaging
    "mongodb": ["mongodb", "mongo"],
    "redis": ["redis"],
    "postgresql": ["postgresql", "postgres"],
    "elasticsearch": ["elasticsearch"],
    "firebase": ["firebase"],
    "supabase": ["supabase"],
    "kafka": ["kafka", "apache kafka"],
    "rabbitmq": ["rabbitmq"],
    # Mobile & Cross-Platform
    "flutter": ["flutter"],
    "react native": ["react native"],
    "android": ["android development", "android studio"],
    # Core CS, API & Testing
    "data structures": ["data structures", "dsa", "algorithms"],
    "system design": ["system design", "distributed systems", "microservices"],
    "rest api": ["rest api", "restful api", "restful", "api development"],
    "graphql": ["graphql"],
    "postman": ["postman"],
    "pytest": ["pytest", "unit testing"],
    "agile": ["agile", "scrum", "kanban"],
    "communication": ["communication", "team collaboration", "technical writing"],
    "problem solving": ["problem solving", "analytical skills"],
}


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


class ResumeAnalysisResult(dict):
    """
    Standardized output conforming strictly to both AVSAR ResumeAnalysisResponse
    frontend API contract and Member 2's backend ResumeAnalysis schema.
    """

    def __init__(
        self,
        parsed_skills: list[str],
        experience_years: float,
        education: list[dict[str, Any]],
        readiness_score: float,
        recommendations: list[str],
        matched_skills: list[str] | None = None,
        missing_skills: list[str] | None = None,
        owner_id: str | None = None,
        document_id: str | None = None,
        evidence: list[dict[str, Any]] | None = None,
        disclaimer: str = "Resume claims; confirm explicitly through profile updates",
    ) -> None:
        self.parsed_skills = parsed_skills
        self.experience_years = experience_years
        self.education = education
        self.readiness_score = readiness_score
        self.recommendations = recommendations
        self.matched_skills = matched_skills or []
        self.missing_skills = missing_skills or []
        self.owner_id = owner_id
        self.document_id = document_id
        self.evidence = evidence or []
        self.disclaimer = disclaimer

        # If owner_id and document_id are supplied, populate dict with exact fields required by Member 2 ResumeAnalysis:
        if owner_id is not None and document_id is not None:
            super().__init__(
                owner_id=owner_id,
                document_id=document_id,
                skills=parsed_skills,
                evidence=self.evidence,
                parsed_skills=parsed_skills,
                experience_years=self.experience_years,
                education=self.education,
                readiness_score=round(self.readiness_score, 1),
                recommendations=self.recommendations,
                warnings=[
                    "Rule-based estimates; absence of evidence is not proof of no experience"
                ],
                disclaimer=self.disclaimer,
            )
        else:
            payload: dict[str, Any] = {
                "parsed_skills": self.parsed_skills,
                "experience_years": round(self.experience_years, 1),
                "education": self.education,
                "readiness_score": round(self.readiness_score, 1),
                "recommendations": self.recommendations,
            }
            if self.matched_skills:
                payload["matched_skills"] = self.matched_skills
            if self.missing_skills:
                payload["missing_skills"] = self.missing_skills
            super().__init__(payload)

    @property
    def skills(self) -> list[str]:
        """Field alias matching backend ResumeAnalysis schema."""
        return self.parsed_skills

    def to_dict(self) -> dict[str, Any]:
        """Convert to API contract JSON structure."""
        return dict(self)


# ---------------------------------------------------------------------------
# Extraction Functions
# ---------------------------------------------------------------------------


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extracts raw text from PDF document bytes using PyMuPDF."""
    if not pdf_bytes:
        return ""
    try:
        with pymupdf.open(stream=BytesIO(pdf_bytes), filetype="pdf") as doc:
            pages = [page.get_text("text").strip() for page in doc]
            return "\n\n".join(filter(None, pages))
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to extract text from PDF: %s", e)
        return ""


def extract_skills_with_evidence(
    text: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    """
    Extracts canonical skills from resume text along with exact text quotes,
    character offsets, and evidence provenance for backend verification.
    """
    if not text:
        return [], []

    normalized_text = text.lower()
    extracted: set[str] = set()
    evidence: list[dict[str, Any]] = []

    for canonical, aliases in SKILL_TAXONOMY.items():
        for alias in aliases:
            # Word boundary regex avoiding partial matches
            pattern = rf"(?<![a-zA-Z0-9_#+]){re.escape(alias)}(?![a-zA-Z0-9_#+])"
            for match in re.finditer(pattern, normalized_text):
                # Check for explicit negative context directly qualifying the skill (e.g. "no knowledge of Docker")
                start_idx = max(0, match.start() - 60)
                prefix = normalized_text[start_idx : match.start()]
                negation_pattern = r"\b(?:no|not|without|zero|lack(?:ing)?|never|unfamiliar)\b(?:[^\.\!\?\n]{1,40})\s*$"
                if re.search(negation_pattern, prefix):
                    continue

                extracted.add(canonical)
                quote_val = text[match.start() : match.end()]
                evidence.append(
                    {
                        "skill": canonical,
                        "quote": quote_val,
                        "start": match.start(),
                        "end": match.end(),
                        "source": "RESUME_CLAIM",
                    }
                )
                break

    return sorted(extracted), evidence


def extract_skills(text: str) -> list[str]:
    """
    Extracts canonical skills from resume text using taxonomy matching,
    regex word boundaries, and negative context checks.
    """
    skills, _ = extract_skills_with_evidence(text)
    return skills


def extract_education(text: str) -> list[dict[str, Any]]:
    """Extracts degrees, institutions, and graduation years from resume text."""
    if not text:
        return []

    education_records: list[dict[str, Any]] = []

    # Degree patterns
    degree_patterns = [
        (
            r"\b(B\.?Tech|B\.?E\.?|Bachelor\s+of\s+Technology|Bachelor\s+of\s+Engineering)\b",
            "B.Tech",
        ),
        (
            r"\b(M\.?Tech|M\.?E\.?|Master\s+of\s+Technology|Master\s+of\s+Engineering)\b",
            "M.Tech",
        ),
        (r"\b(B\.?C\.?A\.?|Bachelor\s+of\s+Computer\s+Applications)\b", "BCA"),
        (r"\b(M\.?C\.?A\.?|Master\s+of\s+Computer\s+Applications)\b", "MCA"),
        (r"\b(B\.?Sc|B\.?S\.?|Bachelor\s+of\s+Science)\b", "B.Sc"),
        (r"\b(M\.?Sc|M\.?S\.?|Master\s+of\s+Science)\b", "M.Sc"),
        (r"\b(Ph\.?D|Doctor\s+of\s+Philosophy)\b", "Ph.D"),
        (r"\b(M\.?B\.?A\.?|Master\s+of\s+Business\s+Administration)\b", "MBA"),
        (r"\b(Higher\s+Secondary|Class\s+12th?|12th\s+Grade|HSC)\b", "Class 12th"),
    ]

    # Major / Branch patterns
    branch_pattern = re.search(
        r"\b(Computer\s+Science|Information\s+Technology|Mechanical|Electrical|Electronics|Civil|Data\s+Science|Artificial\s+Intelligence)\b",
        text,
        re.IGNORECASE,
    )
    branch = branch_pattern.group(0).title() if branch_pattern else None

    # Graduation year pattern (1990 - 2035)
    years = [int(y) for y in re.findall(r"\b(199\d|20[0-3]\d)\b", text)]
    grad_year = max(years) if years else None

    # Institution name pattern
    inst_match = re.search(
        r"(?:at|from|,)?\s*([A-Z][A-Za-z0-9\s,&.-]+(?:University|Institute|College|Academy|IIT|NIT|IIIT|BITS|School))\b",
        text,
    )
    institution = inst_match.group(1).strip() if inst_match else None

    found_degrees: set[str] = set()
    for regex, standard_degree in degree_patterns:
        if re.search(regex, text, re.IGNORECASE):
            found_degrees.add(standard_degree)

    if found_degrees:
        for deg in found_degrees:
            education_records.append(
                {
                    "degree": deg,
                    "field": branch,
                    "institution": institution,
                    "graduation_year": grad_year,
                }
            )
    elif institution or grad_year:
        education_records.append(
            {
                "degree": "Higher Education",
                "field": branch,
                "institution": institution,
                "graduation_year": grad_year,
            }
        )

    return education_records


def estimate_experience_years(text: str) -> float:
    """
    Estimates total years of professional/internship experience
    from explicit statements and date ranges.
    """
    if not text:
        return 0.0

    # 1. Explicit statements like "3 years of experience" or "1.5+ years experience"
    explicit_match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*\+?\s*years?(?:\s+of)?\s+(?:professional\s+|relevant\s+|industry\s+)?experience\b",
        text,
        re.IGNORECASE,
    )
    if explicit_match:
        try:
            return min(float(explicit_match.group(1)), 40.0)
        except ValueError:
            pass

    # 2. Date ranges like "Jan 2022 - Mar 2024" or "2021 - Present"
    current_year = datetime.now().year
    month_names = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
    range_regex = rf"\b(?:{month_names})[a-z]*\s+(\d{{4}})\s*[-–to]+\s*(?:(?:{month_names})[a-z]*\s+)?(\d{{4}}|Present|Current)\b"

    total_months = 0
    matches = re.findall(range_regex, text, re.IGNORECASE)

    for start_year_str, end_year_str in matches:
        start_year = int(start_year_str)
        if start_year < 1980 or start_year > current_year:
            continue
        end_year = (
            current_year if end_year_str.lower() in {"present", "current"} else int(end_year_str)
        )
        if end_year >= start_year:
            # Estimate roughly 12 months per calendar year spanned
            diff_years = max(end_year - start_year, 0.5)
            total_months += diff_years * 12

    if total_months > 0:
        years = total_months / 12.0
        return min(round(years, 1), 35.0)

    # 3. Simple standalone year ranges "2022 - 2024" in experience sections
    simple_years = re.findall(
        r"\b(20[1-2]\d)\s*[-–]\s*(20[1-2]\d|Present|Current)\b", text, re.IGNORECASE
    )
    if simple_years:
        spans = []
        for sy, ey in simple_years:
            s = int(sy)
            e = current_year if ey.lower() in {"present", "current"} else int(ey)
            if 0 <= (e - s) <= 10:
                spans.append(max(e - s, 0.5))
        if spans:
            return round(min(sum(spans), 30.0), 1)

    return 0.0


# ---------------------------------------------------------------------------
# High-Level Service Class
# ---------------------------------------------------------------------------


class ResumeAnalyzer:
    """Service analyzing candidate resumes, extracting credentials, and evaluating readiness."""

    def analyze_text(
        self,
        resume_text: str,
        owner_id: str | None = None,
        document_id: str | None = None,
    ) -> ResumeAnalysisResult:
        """Analyzes plain resume text without specific opportunity context."""
        skills, evidence = extract_skills_with_evidence(resume_text)
        education = extract_education(resume_text)
        exp_years = estimate_experience_years(resume_text)

        # Baseline readiness based on resume completeness
        score = 40.0
        recommendations: list[str] = []

        if len(skills) >= 5:
            score += 25.0
        elif len(skills) >= 2:
            score += 15.0
        else:
            recommendations.append(
                "Add key technical and soft skills to improve resume visibility."
            )

        if education:
            score += 20.0
        else:
            recommendations.append(
                "Include your highest degree, institution name, and graduation year."
            )

        if exp_years > 0:
            score += 15.0
        else:
            recommendations.append(
                "Highlight academic projects, hackathons, or internships to demonstrate practical experience."
            )

        readiness_score = min(max(score, 10.0), 100.0)

        return ResumeAnalysisResult(
            parsed_skills=skills,
            experience_years=exp_years,
            education=education,
            readiness_score=readiness_score,
            recommendations=recommendations,
            owner_id=owner_id,
            document_id=document_id,
            evidence=evidence,
        )

    def analyze_pdf(
        self,
        pdf_bytes: bytes,
        owner_id: str | None = None,
        document_id: str | None = None,
    ) -> ResumeAnalysisResult:
        """Parses a resume PDF and performs credential extraction."""
        text = extract_text_from_pdf_bytes(pdf_bytes)
        return self.analyze_text(text, owner_id=owner_id, document_id=document_id)

    def match_against_opportunity(
        self,
        resume_input: str | bytes,
        opportunity: dict[str, Any],
        owner_id: str | None = None,
        document_id: str | None = None,
    ) -> ResumeAnalysisResult:
        """
        Matches a resume (text or PDF bytes) against an opportunity's requirements,
        calculates gap analysis, and produces a customized readiness score.
        """
        if isinstance(resume_input, bytes):
            resume_text = extract_text_from_pdf_bytes(resume_input)
        else:
            resume_text = resume_input

        base_result = self.analyze_text(resume_text, owner_id=owner_id, document_id=document_id)
        candidate_skills = set(base_result.parsed_skills)

        # Extract required skills from opportunity
        opp_required: list[str] = []
        if isinstance(opportunity.get("required_skills"), list):
            opp_required.extend([s.lower().strip() for s in opportunity["required_skills"]])

        # If required_skills not explicitly listed, search opportunity text for skills
        if not opp_required:
            desc_text = f"{opportunity.get('title', '')} {opportunity.get('description', '')}"
            opp_required = extract_skills(desc_text)

        matched: list[str] = []
        missing: list[str] = []

        for req in opp_required:
            if req in candidate_skills:
                matched.append(req)
            else:
                missing.append(req)

        # Match score calculation
        if opp_required:
            skill_ratio = len(matched) / len(opp_required)
            match_score = skill_ratio * 70.0
        else:
            match_score = 50.0

        # Experience alignment bonus
        exp_score = min(base_result.experience_years * 10.0, 20.0)
        edu_score = 10.0 if base_result.education else 0.0

        final_readiness = min(max(match_score + exp_score + edu_score, 0.0), 100.0)

        # Actionable recommendations
        recs: list[str] = []
        if missing:
            skills_str = ", ".join(f"'{m}'" for m in missing[:5])
            recs.append(
                f"Missing required skills: {skills_str}. Consider building projects or taking certifications in these areas."
            )
        if matched:
            recs.append(f"Strong skill alignment on: {', '.join(matched[:4])}.")

        category = str(opportunity.get("category", "")).lower()
        if category in {"job", "internship"} and base_result.experience_years == 0.0:
            recs.append(
                "Highlight open-source contributions or technical coursework to compensate for limited work experience."
            )

        if not recs:
            recs.append("Profile is well-aligned with this opportunity.")

        return ResumeAnalysisResult(
            parsed_skills=base_result.parsed_skills,
            experience_years=base_result.experience_years,
            education=base_result.education,
            readiness_score=final_readiness,
            recommendations=recs,
            matched_skills=matched,
            missing_skills=missing,
            owner_id=owner_id,
            document_id=document_id,
            evidence=base_result.evidence,
        )


# Global default instance
_analyzer_instance = ResumeAnalyzer()


def analyze_resume(
    resume_input: str | bytes,
    opportunity_or_owner: dict[str, Any] | str | None = None,
    document_id: str | None = None,
    *,
    opportunity: dict[str, Any] | None = None,
    owner_id: str | None = None,
) -> ResumeAnalysisResult:
    """
    Explicit, type-safe convenience function analyzing resume text or PDF bytes.
    Supports both Member 3 frontend opportunity matching and Member 2 backend document tracking.
    """
    target_opp = opportunity
    resolved_owner = owner_id
    resolved_doc = document_id

    if isinstance(opportunity_or_owner, dict):
        target_opp = opportunity_or_owner
    elif isinstance(opportunity_or_owner, str):
        resolved_owner = opportunity_or_owner

    if target_opp:
        return _analyzer_instance.match_against_opportunity(
            resume_input, target_opp, owner_id=resolved_owner, document_id=resolved_doc
        )
    if isinstance(resume_input, bytes):
        return _analyzer_instance.analyze_pdf(
            resume_input, owner_id=resolved_owner, document_id=resolved_doc
        )
    return _analyzer_instance.analyze_text(
        resume_input, owner_id=resolved_owner, document_id=resolved_doc
    )
