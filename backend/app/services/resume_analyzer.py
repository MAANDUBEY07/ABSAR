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

TECHNICAL_SKILLS_TAXONOMY: dict[str, list[str]] = {
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
}

SOFT_SKILLS_TAXONOMY: dict[str, list[str]] = {
    "project management": ["project management", "project planning", "scrum master"],
    "public relations": ["public relations", "pr", "media relations"],
    "teamwork": ["teamwork", "team collaboration", "collaborative", "collaborator"],
    "time management": ["time management", "prioritization", "multitasking"],
    "leadership": ["leadership", "team leadership", "mentor", "mentoring", "people management"],
    "effective communication": [
        "effective communication",
        "communication",
        "verbal communication",
        "written communication",
    ],
    "critical thinking": ["critical thinking", "critical analysis"],
    "problem solving": ["problem solving", "troubleshooting", "analytical thinking"],
    "adaptability": ["adaptability", "flexibility"],
    "negotiation": ["negotiation", "conflict resolution"],
}

# Unified taxonomy dictionary for reverse lookups & backwards compatibility
SKILL_TAXONOMY: dict[str, list[str]] = {**TECHNICAL_SKILLS_TAXONOMY, **SOFT_SKILLS_TAXONOMY}

COMMON_LANGUAGES = [
    "English",
    "French",
    "German",
    "Spanish",
    "Hindi",
    "Mandarin",
    "Chinese",
    "Japanese",
    "Russian",
    "Arabic",
    "Portuguese",
    "Italian",
    "Dutch",
    "Korean",
    "Bengali",
    "Telugu",
    "Marathi",
    "Tamil",
    "Urdu",
    "Gujarati",
    "Kannada",
    "Malayalam",
    "Punjabi",
]


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
        technical_skills: list[str] | None = None,
        soft_skills: list[str] | None = None,
        languages: list[dict[str, str]] | None = None,
        readiness_breakdown: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
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
        self.technical_skills = technical_skills or []
        self.soft_skills = soft_skills or []
        self.languages = languages or []
        self.readiness_breakdown = readiness_breakdown
        self.warnings = warnings or [
            "Rule-based estimates; absence of evidence is not proof of no experience"
        ]
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
                technical_skills=self.technical_skills,
                soft_skills=self.soft_skills,
                languages=self.languages,
                experience_years=self.experience_years,
                education=self.education,
                readiness_score=round(self.readiness_score, 1),
                readiness_breakdown=self.readiness_breakdown,
                recommendations=self.recommendations,
                warnings=self.warnings,
                disclaimer=self.disclaimer,
            )
        else:
            payload: dict[str, Any] = {
                "parsed_skills": self.parsed_skills,
                "technical_skills": self.technical_skills,
                "soft_skills": self.soft_skills,
                "languages": self.languages,
                "experience_years": round(self.experience_years, 1),
                "education": self.education,
                "readiness_score": round(self.readiness_score, 1),
                "readiness_breakdown": self.readiness_breakdown,
                "recommendations": self.recommendations,
                "warnings": self.warnings,
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
) -> tuple[list[str], list[str], list[str], list[dict[str, Any]]]:
    """
    Extracts canonical skills from resume text along with exact text quotes,
    character offsets, and evidence provenance for backend verification.
    Returns: (all_skills, technical_skills, soft_skills, evidence)
    """
    if not text:
        return [], [], [], []

    normalized_text = text.lower()
    extracted_tech: set[str] = set()
    extracted_soft: set[str] = set()
    evidence: list[dict[str, Any]] = []

    def _scan(taxonomy: dict[str, list[str]], target_set: set[str]):
        for canonical, aliases in taxonomy.items():
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

                    target_set.add(canonical)
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

    _scan(TECHNICAL_SKILLS_TAXONOMY, extracted_tech)
    _scan(SOFT_SKILLS_TAXONOMY, extracted_soft)

    tech_sorted = sorted(extracted_tech)
    soft_sorted = sorted(extracted_soft)
    all_sorted = sorted(extracted_tech | extracted_soft)
    return all_sorted, tech_sorted, soft_sorted, evidence


def extract_skills(text: str) -> list[str]:
    """
    Extracts canonical skills from resume text using taxonomy matching,
    regex word boundaries, and negative context checks.
    """
    all_skills, _, _, _ = extract_skills_with_evidence(text)
    return all_skills


def extract_languages(text: str) -> list[dict[str, str]]:
    """Extracts spoken and written languages with proficiency ratings from resume text."""
    if not text:
        return []

    pattern = rf"\b({'|'.join(COMMON_LANGUAGES)})\s*(?:\(([^)]+)\)|[-–:]\s*([A-Za-z]+)\b)"
    results: dict[str, str] = {}
    for match in re.finditer(pattern, text, re.IGNORECASE):
        lang = match.group(1).title()
        prof_raw = (match.group(2) or match.group(3) or "Proficient").strip().title()
        if prof_raw.lower() in ("basics", "basic"):
            prof = "Basic"
        elif prof_raw.lower() in ("fluent", "native"):
            prof = "Fluent"
        elif prof_raw.lower() in ("intermediate", "conversational", "working"):
            prof = "Intermediate"
        elif prof_raw.lower() in ("advanced", "professional"):
            prof = "Advanced"
        else:
            prof = prof_raw
        if lang not in results:
            results[lang] = prof

    return [{"language": lang, "proficiency": prof} for lang, prof in sorted(results.items())]


def extract_education(text: str) -> list[dict[str, Any]]:
    """Extracts degrees, institutions, GPA, and graduation years from resume text."""
    if not text:
        return []

    # 1. Institutions: Look for standard institution names
    inst_matches = re.findall(
        r"^[ \t]*([A-Za-z0-9 &.,-]{2,80}?(?:University|Institute(?:\s+of\s+[A-Za-z]+)?|College|Academy|IIT|NIT|IIIT|BITS|School)[A-Za-z0-9 &.,-]*)",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    institution = None
    if inst_matches:
        cleaned_candidates = [
            re.sub(r"[,0-9\s]+$", "", m.strip()).strip().title()
            for m in inst_matches
            if len(m.strip()) > 3
        ]
        if cleaned_candidates:
            institution = max(set(cleaned_candidates), key=cleaned_candidates.count)

    # 2. GPA extraction
    gpa_match = re.search(
        r"\b(?:GPA|CGPA)\s*:\s*([0-9\.]+)\s*(?:/\s*([0-9\.]+))?\b", text, re.IGNORECASE
    )
    gpa_str = None
    if gpa_match:
        score = gpa_match.group(1)
        max_score = gpa_match.group(2)
        gpa_str = f"{score} / {max_score}" if max_score else score

    # 3. Collapse text for degree pattern matching across line breaks
    collapsed = re.sub(r"\s+", " ", text)

    # Degree patterns (ordered: specific degrees first, then generic)
    degree_patterns = [
        (
            r"\b(Master\s+of\s+Business\s+Management|M\.?B\.?M\.?)\b",
            "Master of Business Management",
            "Business Management",
        ),
        (
            r"\b(Master\s+of\s+Business\s+Administration|M\.?B\.?A\.?)\b",
            "MBA",
            "Business Administration",
        ),
        (
            r"\b(Bachelor\s+of\s+Business\s+Administration|B\.?B\.?A\.?)\b",
            "BBA",
            "Business Administration",
        ),
        (
            r"\b(Bachelor\s+of\s+Business\s+Management|B\.?B\.?M\.?)\b",
            "BBM",
            "Business Management",
        ),
        (
            r"\b(Bachelor\s+of\s+Business)\b",
            "Bachelor of Business",
            "Business",
        ),
        (
            r"\b(Master\s+of\s+Business)\b",
            "Master of Business",
            "Business",
        ),
        (
            r"\b(B\.?Tech|B\.?E\.?|Bachelor\s+of\s+Technology|Bachelor\s+of\s+Engineering)\b",
            "B.Tech",
            None,
        ),
        (
            r"\b(M\.?Tech|M\.?E\.?|Master\s+of\s+Technology|Master\s+of\s+Engineering)\b",
            "M.Tech",
            None,
        ),
        (r"\b(B\.?C\.?A\.?|Bachelor\s+of\s+Computer\s+Applications)\b", "BCA", "Computer Applications"),
        (r"\b(M\.?C\.?A\.?|Master\s+of\s+Computer\s+Applications)\b", "MCA", "Computer Applications"),
        (r"\b(B\.?Sc|B\.?S\.?|Bachelor\s+of\s+Science)\b", "B.Sc", None),
        (r"\b(M\.?Sc|M\.?S\.?|Master\s+of\s+Science)\b", "M.Sc", None),
        (r"\b(Ph\.?D|Doctor\s+of\s+Philosophy)\b", "Ph.D", None),
        (r"\b(Higher\s+Secondary|Class\s+12th?|12th\s+Grade|HSC)\b", "Class 12th", None),
    ]

    # Major / Branch patterns
    branch_pattern = re.search(
        r"\b(Computer\s+Science|Information\s+Technology|Mechanical|Electrical|Electronics|Civil|Data\s+Science|Artificial\s+Intelligence)\b",
        text,
        re.IGNORECASE,
    )
    fallback_branch = branch_pattern.group(0).title() if branch_pattern else None

    education_records: list[dict[str, Any]] = []
    seen_degrees: set[str] = set()

    for regex, standard_degree, degree_field in degree_patterns:
        match = re.search(regex, collapsed, re.IGNORECASE)
        if match:
            # Avoid duplicate or subset matches (e.g. Master of Business vs Master of Business Management)
            if any(standard_degree in s for s in seen_degrees):
                continue
            seen_degrees.add(standard_degree)

            # Look for start/end years near this degree
            window = collapsed[max(0, match.start() - 100) : min(len(collapsed), match.end() + 100)]
            year_range = re.findall(r"\b(20[0-3]\d|199\d)\s*[-–]\s*(20[0-3]\d|199\d)\b", window)
            grad_year = None
            start_year = None
            if year_range:
                sy, ey = year_range[0]
                start_year = int(sy)
                grad_year = int(ey)
            else:
                years = [int(y) for y in re.findall(r"\b(199\d|20[0-3]\d)\b", window)]
                if years:
                    grad_year = max(years)

            field = degree_field or fallback_branch
            record: dict[str, Any] = {
                "degree": standard_degree,
                "field": field,
                "institution": institution,
                "graduation_year": grad_year,
            }
            if start_year:
                record["start_year"] = start_year
            if gpa_str and (("Bachelor" in standard_degree or "B." in standard_degree) or len(seen_degrees) == 1):
                record["gpa"] = gpa_str

            education_records.append(record)

    # Fallback if no specific degree found but institution or year present
    if not education_records and (institution or re.findall(r"\b(199\d|20[0-3]\d)\b", text)):
        all_years = [int(y) for y in re.findall(r"\b(199\d|20[0-3]\d)\b", text)]
        education_records.append(
            {
                "degree": "Higher Education",
                "field": fallback_branch,
                "institution": institution,
                "graduation_year": max(all_years) if all_years else None,
                "gpa": gpa_str,
            }
        )

    return education_records


def estimate_experience_years_with_warnings(text: str) -> tuple[float, list[str]]:
    """
    Estimates total years of completed professional/internship experience
    from explicit statements and employment date ranges, capping ongoing
    roles at the current year and flagging future-dated entries.
    Returns: (experience_years, warnings)
    """
    if not text:
        return 0.0, []

    current_year = datetime.now().year
    warnings: list[str] = []

    # 1. Explicit statements like "3 years of experience" or "1.5+ years experience"
    explicit_match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*\+?\s*years?(?:\s+of)?\s+(?:professional\s+|relevant\s+|industry\s+)?experience\b",
        text,
        re.IGNORECASE,
    )
    if explicit_match:
        try:
            return min(float(explicit_match.group(1)), 40.0), warnings
        except ValueError:
            pass

    # 2. Extract experience section if available to prevent picking up education year ranges
    exp_header = re.search(
        r"\b(work\s+experience|professional\s+experience|employment\s+history|experience)\b",
        text,
        re.IGNORECASE,
    )
    edu_header = re.search(
        r"\b(education|academic\s+background|qualifications)\b",
        text,
        re.IGNORECASE,
    )

    if exp_header and edu_header and edu_header.start() > exp_header.start():
        exp_text = text[exp_header.start() : edu_header.start()]
    elif exp_header:
        exp_text = text[exp_header.start() :]
    else:
        exp_text = text

    norm_exp = re.sub(r"\s+", " ", exp_text)
    month_names = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
    month_range_regex = rf"\b(?:{month_names})[a-z]*\s+(\d{{4}})\s*[-–to]+\s*(?:(?:{month_names})[a-z]*\s+)?(\d{{4}}|Present|Current)\b"
    year_range_regex = r"\b(199\d|20[0-3]\d)\s*[-–]\s*(199\d|20[0-3]\d|Present|Current)\b"

    raw_matches = re.findall(month_range_regex, norm_exp, re.IGNORECASE) + re.findall(
        year_range_regex, norm_exp, re.IGNORECASE
    )

    valid_intervals: list[tuple[int, int]] = []
    seen_pairs: set[tuple[str, str]] = set()

    for sy_str, ey_str in raw_matches:
        pair_key = (sy_str.strip().lower(), ey_str.strip().lower())
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        sy = int(sy_str)
        is_present = ey_str.lower() in ("present", "current")
        ey = current_year if is_present else int(ey_str)

        if sy > current_year:
            warnings.append(
                f"Future-dated employment entry detected ({sy_str} - {ey_str}); future periods are not counted as completed experience."
            )
            continue

        effective_ey = min(ey, current_year)
        if ey > current_year:
            warnings.append(
                f"Ongoing entry ({sy_str} - {ey_str}) extends past current year; completed experience counted through {current_year}."
            )

        if effective_ey >= sy:
            valid_intervals.append((sy, effective_ey))

    if not valid_intervals:
        return 0.0, warnings

    valid_intervals.sort()
    merged: list[list[int]] = []
    for s, e in valid_intervals:
        if not merged:
            merged.append([s, e])
        else:
            prev_s, prev_e = merged[-1]
            if s <= prev_e:
                merged[-1][1] = max(prev_e, e)
            else:
                merged.append([s, e])

    total_years = sum(max(e - s, 0.5 if e == s else 0.0) for s, e in merged)
    return min(round(total_years, 1), 35.0), warnings


def estimate_experience_years(text: str) -> float:
    """
    Estimates total years of professional/internship experience
    from explicit statements and date ranges.
    """
    years, _ = estimate_experience_years_with_warnings(text)
    return years


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
        all_skills, tech_skills, soft_skills, evidence = extract_skills_with_evidence(resume_text)
        education = extract_education(resume_text)
        exp_years, date_warnings = estimate_experience_years_with_warnings(resume_text)
        languages = extract_languages(resume_text)

        # Baseline readiness based on resume completeness breakdown
        has_contact = bool(
            re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", resume_text)
            or re.search(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", resume_text)
        )
        contact_score = 10.0 if has_contact else 0.0
        education_score = 25.0 if education else 0.0
        exp_score = 25.0 if exp_years > 0 else 0.0
        tech_score = min(len(tech_skills) * 5.0, 20.0)
        soft_lang_score = min(len(soft_skills) * 2.0 + len(languages) * 2.5, 20.0)

        total_score = contact_score + education_score + exp_score + tech_score + soft_lang_score
        readiness_score = min(max(total_score, 10.0), 100.0)

        breakdown = {
            "contact_score": contact_score,
            "education_score": education_score,
            "experience_score": exp_score,
            "technical_skills_score": tech_score,
            "soft_skills_and_languages_score": soft_lang_score,
            "total_score": round(readiness_score, 1),
            "score_type": "RESUME_COMPLETENESS",
            "explanation": (
                "Calculated based on resume profile completeness (contact info, education credentials, "
                "work experience history, technical/soft skills, and languages). Match readiness against "
                "specific opportunities is evaluated during opportunity comparison."
            ),
        }

        recommendations: list[str] = []
        if not tech_skills:
            recommendations.append(
                "Add relevant technical and domain tools to demonstrate specialization for technical roles."
            )
        if not education:
            recommendations.append(
                "Include your highest degree, institution name, and graduation year."
            )
        if exp_years == 0:
            recommendations.append(
                "Highlight academic projects, hackathons, or internships to demonstrate practical experience."
            )
        if not languages:
            recommendations.append(
                "List spoken and written languages with proficiency levels to enhance global profile visibility."
            )

        all_warnings = list(date_warnings)
        all_warnings.append(
            "Rule-based estimates; absence of evidence is not proof of no experience"
        )

        return ResumeAnalysisResult(
            parsed_skills=all_skills,
            experience_years=exp_years,
            education=education,
            readiness_score=readiness_score,
            recommendations=recommendations,
            technical_skills=tech_skills,
            soft_skills=soft_skills,
            languages=languages,
            readiness_breakdown=breakdown,
            warnings=all_warnings,
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

        # Fallback 1: opportunity tags
        if not opp_required:
            tags = opportunity.get("category_metadata", {}).get("tags", [])
            if isinstance(tags, list):
                opp_required.extend([t.lower().strip() for t in tags if isinstance(t, str)])

        # Fallback 2: search opportunity title & description for taxonomy skills
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
            technical_skills=base_result.technical_skills,
            soft_skills=base_result.soft_skills,
            languages=base_result.languages,
            readiness_breakdown=base_result.readiness_breakdown,
            warnings=base_result.warnings,
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
