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
    "sql": ["sql", "mysql", "sqlite", "tsql", "plsql"],
    "postgresql": ["postgresql", "postgres"],
    "bigquery": ["bigquery", "google bigquery"],
    "r": ["r programming", "r language", r"(?<=[\s,(])r(?=[\s,)]|$)"],
    "bash": ["bash", "shell scripting", "shell script"],
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
    "html": ["html", "html5"],
    "css": ["css", "css3", "sass", "tailwind", "bootstrap"],
    "php": ["php"],
    "ruby": ["ruby", "ruby on rails"],

    # AI, ML & Data Science
    "machine learning": ["machine learning", "ml", "pattern recognition"],
    "deep learning": ["deep learning", "dl", "neural networks"],
    "pytorch": ["pytorch"],
    "tensorflow": ["tensorflow", "tf", "keras"],
    "scikit-learn": ["scikit-learn", "sklearn"],
    "xgboost": ["xgboost"],
    "lightgbm": ["lightgbm"],
    "hugging face transformers": [
        "hugging face transformers",
        "hugging face",
        "huggingface",
        "transformers",
    ],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "nlp": ["nlp", "natural language processing", "spacy", "nltk", "distilbert", "bert"],
    "computer vision": ["computer vision", "opencv"],
    "generative ai": ["generative ai", "genai", "llm", "large language models"],
    "langchain": ["langchain", "llamaindex", "rag"],
    "hdbscan": ["hdbscan"],
    "smote": ["smote"],
    "isolation forests": ["isolation forests", "isolation forest"],
    "prophet": ["prophet"],
    "gradient boosting": ["gradient boosting"],

    # Data Engineering & Cloud
    "pyspark": ["pyspark", "spark", "apache spark"],
    "apache airflow": ["apache airflow", "airflow"],
    "dbt": ["dbt"],
    "docker": ["docker", "containerization"],
    "kubernetes": ["kubernetes", "k8s"],
    "aws sagemaker": ["aws sagemaker", "sagemaker"],
    "s3": ["aws s3", "s3", "amazon s3"],
    "ec2": ["aws ec2", "ec2", "amazon ec2"],
    "aws": ["aws", "amazon web services"],
    "azure": ["azure", "microsoft azure"],
    "gcp": ["gcp", "google cloud", "google cloud platform"],
    "mlflow": ["mlflow"],
    "fastapi": ["fastapi", "fast-api"],
    "git": ["git", "github", "gitlab", "version control"],
    "terraform": ["terraform"],
    "ansible": ["ansible"],
    "ci/cd": ["ci/cd", "continuous integration", "github actions", "jenkins"],
    "linux": ["linux", "ubuntu"],

    # Experimentation, Statistics & BI
    "a/b testing": ["a/b testing", "ab testing", "split testing", "stratified a/b"],
    "causal inference": ["causal inference"],
    "bayesian statistics": ["bayesian statistics", "bayesian"],
    "tableau": ["tableau"],
    "matplotlib": ["matplotlib"],
    "seaborn": ["seaborn"],

    # Frameworks & Libraries
    "react": ["react", "react.js", "reactjs", "react native"],
    "node.js": ["node", "node.js", "nodejs"],
    "next.js": ["next.js", "nextjs"],
    "django": ["django", "django rest framework", "drf"],
    "flask": ["flask"],
    "express": ["express", "express.js", "expressjs"],
    "spring boot": ["spring boot", "springboot", "spring framework"],
    "angular": ["angular", "angularjs"],
    "vue.js": ["vue", "vue.js", "vuejs"],
    "tailwind css": ["tailwind", "tailwind css", "tailwindcss"],
    "redux": ["redux", "redux toolkit"],

    # Databases, Storage & Messaging
    "mongodb": ["mongodb", "mongo"],
    "redis": ["redis"],
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
# Skill Categories & Taxonomy Mapping
# ---------------------------------------------------------------------------

SKILL_CATEGORY_MAP: dict[str, list[str]] = {
    "Programming Languages": [
        "python", "sql", "postgresql", "bigquery", "r", "bash", "java", "c++", "c",
        "javascript", "typescript", "go", "rust", "php", "ruby", "scala", "kotlin", "swift", "html", "css"
    ],
    "Machine Learning & AI": [
        "machine learning", "deep learning", "pytorch", "tensorflow", "scikit-learn", "xgboost",
        "lightgbm", "hugging face transformers", "nlp", "computer vision", "generative ai",
        "langchain", "hdbscan", "smote", "isolation forests", "prophet", "gradient boosting"
    ],
    "Data Engineering & Cloud": [
        "pyspark", "apache airflow", "dbt", "docker", "kubernetes", "aws sagemaker", "s3",
        "ec2", "aws", "azure", "gcp", "mlflow", "fastapi", "git", "terraform", "ansible", "ci/cd", "linux"
    ],
    "Experimentation & Analytics": [
        "a/b testing", "causal inference", "bayesian statistics", "tableau", "matplotlib",
        "seaborn", "pandas", "numpy", "statistics"
    ],
    "Frameworks & Web": [
        "react", "node.js", "next.js", "django", "flask", "express", "spring boot"
    ],
    "Databases & Storage": [
        "mongodb", "redis", "mysql", "elasticsearch", "cassandra", "dynamodb", "neo4j"
    ],
}


def categorize_skills(technical_skills: list[str], soft_skills: list[str]) -> dict[str, list[str]]:
    """Groups detected technical and soft skills into structured domain categories."""
    categories: dict[str, list[str]] = {}
    assigned_tech: set[str] = set()

    for cat_name, skill_list in SKILL_CATEGORY_MAP.items():
        matched = [s for s in technical_skills if s.lower() in skill_list]
        if matched:
            categories[cat_name] = sorted(matched)
            assigned_tech.update(matched)

    remaining_tech = [s for s in technical_skills if s not in assigned_tech]
    if remaining_tech:
        categories["Tools & Specialized Technologies"] = sorted(remaining_tech)

    if soft_skills:
        categories["Soft Skills & Professional Competencies"] = sorted(soft_skills)

    return categories


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
        projects: list[dict[str, Any]] | None = None,
        certifications: list[dict[str, Any]] | None = None,
        publications: list[dict[str, Any]] | None = None,
        candidate: dict[str, Any] | None = None,
        experience: list[dict[str, Any]] | None = None,
        skill_categories: dict[str, list[str]] | None = None,
        completeness_score: float | None = None,
        completeness_breakdown: dict[str, Any] | None = None,
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
        self.projects = projects or []
        self.certifications = certifications or []
        self.publications = publications or []
        self.candidate = candidate or {}
        self.experience = experience or []
        self.skill_categories = skill_categories or {}
        self.completeness_score = completeness_score if completeness_score is not None else readiness_score
        self.completeness_breakdown = completeness_breakdown or readiness_breakdown

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
                projects=self.projects,
                certifications=self.certifications,
                publications=self.publications,
                candidate=self.candidate,
                experience=self.experience,
                skill_categories=self.skill_categories,
                completeness_score=round(self.completeness_score, 1),
                completeness_breakdown=self.completeness_breakdown,
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
                "evidence": self.evidence,
                "disclaimer": self.disclaimer,
                "projects": self.projects,
                "certifications": self.certifications,
                "publications": self.publications,
                "candidate": self.candidate,
                "experience": self.experience,
                "skill_categories": self.skill_categories,
                "completeness_score": round(self.completeness_score, 1),
                "completeness_breakdown": self.completeness_breakdown,
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
    Handles multiline PDF text and flexible whitespace.
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
                # Handle regex alias or standard string alias with flexible whitespace across linebreaks
                if alias.startswith("(?<="):
                    pattern = alias
                else:
                    escaped = re.escape(alias)
                    flexible_whitespace = escaped.replace(r"\ ", r"\s+")
                    pattern = rf"(?<![a-zA-Z0-9_#+]){flexible_whitespace}(?![a-zA-Z0-9_#+])"

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


def extract_projects(text: str) -> list[dict[str, Any]]:
    """Extracts structured projects with name, technologies, descriptions, responsibilities, and outcomes."""
    if not text:
        return []

    proj_header = re.search(
        r"\b(?:SELECTED\s+PROJECTS|ACADEMIC\s+PROJECTS|KEY\s+PROJECTS|PROJECTS)\b",
        text,
        re.IGNORECASE,
    )
    if not proj_header:
        return []

    after_proj = text[proj_header.end() :]
    next_header = re.search(
        r"\n\s*(?:EDUCATION|CERTIFICATIONS|PUBLICATIONS|SKILLS|WORK\s+EXPERIENCE|EXPERIENCE)\b",
        after_proj,
        re.IGNORECASE,
    )
    proj_text = after_proj[: next_header.start()] if next_header else after_proj

    raw_lines = [line.strip() for line in proj_text.strip().split("\n") if line.strip()]
    projects: list[dict[str, Any]] = []
    current_proj: dict[str, Any] | None = None
    bullet_re = r"^[\s•·\-\*\u00b7\u2022\u25cf\u25cb\u25aa\u25ab\?\u2013\u2014]"

    for line in raw_lines:
        proj_title_match = re.match(
            r"^([A-Z][A-Za-z0-9\- ]+?(?:Engine|Simulator|Platform|System|Application|Model|Pipeline|Dashboard|Tracker|Tool|Service|Classifier|Detector|Project))\s+([A-Za-z0-9+#.\- ]+,\s*[A-Za-z0-9+#.\- ]+.*)$",
            line,
        )
        if proj_title_match:
            name = proj_title_match.group(1).strip()
            tech_str = proj_title_match.group(2).strip()
            techs = [t.strip() for t in re.split(r"[,|•·]", tech_str) if t.strip()]
            current_proj = {
                "name": name,
                "technologies": techs,
                "description": "",
                "responsibilities": [],
                "outcomes": [],
            }
            projects.append(current_proj)
        elif current_proj is not None:
            is_bullet = bool(re.match(bullet_re, line))
            clean = re.sub(bullet_re, "", line).strip()
            if clean:
                if not current_proj["description"]:
                    current_proj["description"] = clean
                else:
                    current_proj["description"] += " " + clean
                if is_bullet or not current_proj["responsibilities"]:
                    current_proj["responsibilities"].append(clean)
                else:
                    current_proj["responsibilities"][-1] += " " + clean

    for p in projects:
        for r in p["responsibilities"]:
            if re.search(r"(?:\d+%\s*|\d+\+\s*|\b(?:achieving|achieved|improving|improved|reducing|reduced|increasing|increased)\b)", r, re.I):
                p["outcomes"].append(r)

    return projects


def extract_certifications_and_publications(
    text: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Extracts structured certifications and publications."""
    if not text:
        return [], []

    cert_pub_header = re.search(
        r"\b(?:CERTIFICATIONS?\s*(?:&|AND)?\s*PUBLICATIONS?|CERTIFICATIONS?|PUBLICATIONS?|LICENSES?)\b",
        text,
        re.IGNORECASE,
    )
    if not cert_pub_header:
        return [], []

    after_header = text[cert_pub_header.end() :]
    next_header = re.search(
        r"\n\s*(?:EDUCATION|PROJECTS|SKILLS|EXPERIENCE|WORK\s+EXPERIENCE)\b",
        after_header,
        re.IGNORECASE,
    )
    section_text = after_header[: next_header.start()] if next_header else after_header

    raw_lines = [line.strip() for line in section_text.strip().split("\n") if line.strip()]
    merged_lines: list[str] = []
    bullet_re = r"^[\s•·\-\*\u00b7\u2022\u25cf\u25cb\u25aa\u25ab\?\u2013\u2014]+"
    for line in raw_lines:
        clean_prefix = re.sub(bullet_re, "", line).strip()
        is_new_entry = bool(
            re.match(bullet_re, line)
            or re.match(
                r"^(?:AWS|Google|Microsoft|Certified|Certificate|Co-Author|Author|\[\d+\])",
                clean_prefix,
                re.IGNORECASE,
            )
        )
        if merged_lines and not is_new_entry:
            merged_lines[-1] += " " + line
        else:
            merged_lines.append(line)

    certifications: list[dict[str, Any]] = []
    publications: list[dict[str, Any]] = []

    for line in merged_lines:
        clean = re.sub(bullet_re, "", line).strip()
        if re.search(
            r"\b(?:IEEE|Conference|Workshop|Journal|Transactions|Symposium|Co-Author|Author|Paper|Publication)\b",
            clean,
            re.IGNORECASE,
        ) or '"' in clean:
            q_match = re.search(r'"([^"]+)"', clean)
            title = q_match.group(1) if q_match else None
            author_match = re.search(r"\b(Co-Author|First Author|Author)\b", clean, re.IGNORECASE)
            author = author_match.group(1) if author_match else None
            if q_match:
                after_title = clean[q_match.end() :]
                venue = re.sub(r"^[\s—–·\u00b7\-?]+", "", after_title).strip() or None
            else:
                dash_split = re.split(r"\s*[-—–·\u00b7]\s*", clean)
                venue = dash_split[-1].strip() if len(dash_split) > 1 else None

            # Look for year in clean line (preferring parenthesized year or trailing year)
            year_match = re.search(r"\((20[0-3]\d|199\d)\)", clean) or re.search(r"\b(20[0-3]\d|199\d)\b", clean)
            year = int(year_match.group(1)) if year_match else None
            publications.append(
                {
                    "title": title or clean,
                    "authors": author,
                    "venue": venue,
                    "year": year,
                    "source_evidence": clean,
                    "confidence": "EXTRACTED_EXACT",
                }
            )
        elif re.search(
            r"\b(?:Certified|Specialty|Practitioner|Architect|Developer|Certificate|License)\b",
            clean,
            re.IGNORECASE,
        ):
            year_match = re.search(r"\b(20[0-3]\d|199\d)\b", clean)
            year = int(year_match.group(1)) if year_match else None
            issuer = None
            for cand in ["AWS", "Google Cloud", "GCP", "Microsoft Azure", "Azure", "HashiCorp"]:
                if cand.lower() in clean.lower():
                    issuer = cand
                    break
            name = re.sub(r"\s*\((?:Issued|Completed|Verified)?\s*\d{4}\)", "", clean).strip()
            name = re.sub(r"^\s*·\s*", "", name).strip()
            name = re.sub(r"\s*[?]\s*", " – ", name).strip()
            certifications.append(
                {
                    "name": name,
                    "issuer": issuer,
                    "year": year,
                    "source_evidence": clean,
                    "confidence": "EXTRACTED_EXACT",
                }
            )

    return certifications, publications


def extract_education(text: str) -> list[dict[str, Any]]:
    """Extracts degrees, institutions, GPA/CGPA, and graduation years from resume text."""
    if not text:
        return []

    # Isolate education section if present to avoid cross-section year interference
    edu_header = re.search(r"\b(?:EDUCATION|ACADEMIC\s+BACKGROUND|QUALIFICATIONS)\b", text, re.IGNORECASE)
    if edu_header:
        after_header = text[edu_header.end() :]
        next_header = re.search(
            r"\n\s*(?:CERTIFICATIONS|PUBLICATIONS|PROJECTS|SKILLS|WORK\s+EXPERIENCE|EXPERIENCE)\b",
            after_header,
            re.IGNORECASE,
        )
        edu_section = after_header[: next_header.start()] if next_header else after_header
    else:
        edu_section = text

    # 1. GPA / CGPA extraction within education section
    gpa_match = re.search(
        r"\b(?:CGPA|GPA)\s*:\s*([0-9\.]+)\s*(?:/\s*([0-9\.]+))?\b", edu_section, re.IGNORECASE
    )
    gpa_str = None
    if gpa_match:
        score = gpa_match.group(1)
        max_score = gpa_match.group(2)
        gpa_str = f"{score} / {max_score}" if max_score else score

    # 2. Institution extraction: search lines inside education section, then fallback
    inst_candidates = []
    for line in edu_section.split("\n"):
        line_clean = line.strip()
        if not line_clean:
            continue
        parts = [p.strip() for p in line_clean.split("|")]
        for p in parts:
            if re.search(r"\b(?:University|Institute|College|Academy|School|IIIT|IIT|NIT|BITS)\b", p, re.IGNORECASE):
                inst_cand = re.sub(r"\b(?:CGPA|GPA|Grade)\b.*$", "", p, flags=re.IGNORECASE).strip()
                inst_cand = re.sub(r"\b(?:199\d|20[0-3]\d)\b.*$", "", inst_cand).strip()
                inst_cand = inst_cand.strip(" ,.-")
                if len(inst_cand) > 3:
                    if inst_cand.isupper():
                        inst_cand = inst_cand.title()
                    inst_candidates.append(inst_cand)

    institution = inst_candidates[0] if inst_candidates else None
    if not institution:
        inst_matches = re.findall(
            r"^[ \t]*([A-Za-z0-9 &.,-]{2,80}?(?:University|Institute(?:\s+of\s+[A-Za-z]+)?|College|Academy|IIT|NIT|IIIT|BITS|School)[A-Za-z0-9 &.,-]*)",
            text,
            re.IGNORECASE | re.MULTILINE,
        )
        if inst_matches:
            cleaned_candidates = [
                re.sub(r"[,0-9\s]+$", "", m.strip()).strip().title()
                for m in inst_matches
                if len(m.strip()) > 3
            ]
            if cleaned_candidates:
                institution = max(set(cleaned_candidates), key=cleaned_candidates.count)

    collapsed = re.sub(r"\s+", " ", edu_section)

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
            r"\b(B\.?Tech|B\.?E\.?|Bachelor\s+of\s+Technology|Bachelor\s+of\s+Engineering)(?:\s+in\s+([A-Za-z &(),\-]+?))?(?:\s+\d{4}|\s*[-–—]|\s*$)",
            "B.Tech",
            None,
        ),
        (
            r"\b(M\.?Tech|M\.?E\.?|Master\s+of\s+Technology|Master\s+of\s+Engineering)(?:\s+in\s+([A-Za-z &(),\-]+?))?(?:\s+\d{4}|\s*[-–—]|\s*$)",
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

    branch_match = re.search(
        r"\b(?:in\s+)?(Computer\s+Science(?:\s*&\s*Engineering)?(?:\s*\([A-Za-z ]+\))?|Information\s+Technology|Mechanical|Electrical|Electronics|Civil|Data\s+Science|Artificial\s+Intelligence)\b",
        edu_section,
        re.IGNORECASE,
    )
    fallback_branch = branch_match.group(1).strip() if branch_match else None

    education_records: list[dict[str, Any]] = []
    seen_degrees: set[str] = set()

    for regex, standard_degree, degree_field in degree_patterns:
        match = re.search(regex, collapsed, re.IGNORECASE)
        if match:
            if any(standard_degree in s for s in seen_degrees):
                continue
            seen_degrees.add(standard_degree)

            # Year range: inspect after degree first, then before
            after_window = collapsed[match.start() : min(len(collapsed), match.end() + 100)]
            year_range = re.findall(
                r"\b(199\d|20[0-3]\d)\s*[-–—to]+\s*(199\d|20[0-3]\d|Present|Current)\b",
                after_window,
                re.IGNORECASE,
            )
            if not year_range:
                before_window = collapsed[max(0, match.start() - 100) : match.end()]
                year_range = re.findall(
                    r"\b(199\d|20[0-3]\d)\s*[-–—to]+\s*(199\d|20[0-3]\d|Present|Current)\b",
                    before_window,
                    re.IGNORECASE,
                )

            grad_year = None
            start_year = None
            if year_range:
                sy, ey = year_range[0]
                start_year = int(sy)
                grad_year = int(ey) if ey.isdigit() else None
            else:
                years = [int(y) for y in re.findall(r"\b(199\d|20[0-3]\d)\b", after_window)]
                if not years:
                    years = [
                        int(y)
                        for y in re.findall(
                            r"\b(199\d|20[0-3]\d)\b",
                            collapsed[max(0, match.start() - 60) : match.end()],
                        )
                    ]
                if years:
                    grad_year = max(years)

            field = None
            try:
                field = (
                    match.group(2).strip()
                    if (match.lastindex and match.lastindex >= 2 and match.group(2))
                    else None
                )
            except IndexError:
                field = None

            if not field:
                field = degree_field or fallback_branch

            record: dict[str, Any] = {
                "degree": standard_degree,
                "field": field,
                "institution": institution,
                "graduation_year": grad_year,
            }
            if start_year:
                record["start_year"] = start_year
            if gpa_str and (
                ("Bachelor" in standard_degree or "B." in standard_degree)
                or len(seen_degrees) == 1
                or "GPA" in after_window
            ):
                record["gpa"] = gpa_str

            education_records.append(record)

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


def extract_candidate_info(text: str) -> dict[str, Any]:
    """Extracts candidate profile summary: name, title, contact information, location, and social links."""
    if not text:
        return {}

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    name = lines[0] if lines else "Candidate"

    title = None
    for l in lines[1:4]:
        if not re.search(r"@|\+?\d|http|linkedin|github", l, re.IGNORECASE) and len(l) < 50:
            title = l
            break

    email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", text)
    email = email_match.group(0) if email_match else None

    phone_match = re.search(r"(?:\+\d{1,3}[\s-]?)?\(?\d{3,5}\)?[\s-]?\d{3,5}(?:[\s-]?\d{3,5})?", text)
    phone = phone_match.group(0).strip() if phone_match else None

    linkedin_match = re.search(r"(?:linkedin\.com/in/[a-zA-Z0-9\-_]+)", text, re.IGNORECASE)
    linkedin = linkedin_match.group(0) if linkedin_match else None

    github_match = re.search(r"(?:github\.com/[a-zA-Z0-9\-_]+)", text, re.IGNORECASE)
    github = github_match.group(0) if github_match else None

    location = None
    for l in lines[:6]:
        parts = [p.strip() for p in l.split("|")]
        for p in parts:
            if re.search(r"([A-Za-z]+,\s*[A-Za-z]+)", p) and not re.search(
                r"@|\+?\d|http|linkedin|github|scientist|engineer|developer|designer", p, re.IGNORECASE
            ):
                location = p
                break
        if location:
            break

    if not location:
        contact_idx = -1
        for i, l in enumerate(lines):
            if l.upper() == "CONTACT":
                contact_idx = i
                break
        if contact_idx != -1:
            for l in lines[contact_idx + 1 : contact_idx + 5]:
                if not re.search(r"@|\+?\d", l) and len(l) < 60:
                    location = l
                    break

    return {
        "name": name.title() if name.isupper() else name,
        "title": title.title() if title and title.isupper() else title,
        "email": email,
        "phone": phone,
        "location": location,
        "linkedin": linkedin,
        "github": github,
        "source": "RESUME_EXTRACTION",
    }


def extract_experience_entries(text: str) -> list[dict[str, Any]]:
    """
    Extracts structured professional employment entries:
    Job title, organization, location, start and end dates, duration,
    and responsibilities/measurable achievements.
    """
    if not text:
        return []

    exp_header = re.search(
        r"\b(?:WORK\s+EXPERIENCE|PROFESSIONAL\s+EXPERIENCE|EMPLOYMENT\s+HISTORY)\b",
        text,
        re.IGNORECASE,
    )
    if not exp_header:
        return []

    after = text[exp_header.end() :]
    next_header = re.search(
        r"\n\s*(?:EDUCATION|SELECTED\s+PROJECTS|ACADEMIC\s+PROJECTS|PROJECTS|SKILLS|CERTIFICATIONS)\b",
        after,
        re.IGNORECASE,
    )
    exp_text = after[: next_header.start()] if next_header else after

    entries: list[dict[str, Any]] = []
    current_entry: dict[str, Any] | None = None
    lines = [l.strip() for l in exp_text.split("\n") if l.strip()]
    bullet_re = r"^[\s•·\-\*\u00b7\u2022\u25cf\u25cb\u25aa\u25ab\?\u2013\u2014]"

    inline_re = (
        r"^([A-Za-z\s]+?)\s*\|\s*([A-Za-z0-9\s&.,-]+?)(?:,\s*([A-Za-z\s]+))?\s+"
        r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\s*[\-–—\?to]+\s*(\w+(?:\s+\d{4})?)$"
    )
    date_header_re = r"^(\d{4})\s*[\-–—to]+\s*(\d{4}|Present|Current)$"

    i = 0
    while i < len(lines):
        line = lines[i]
        inline_match = re.match(inline_re, line, re.IGNORECASE)
        date_match = re.match(date_header_re, line, re.IGNORECASE)

        if inline_match:
            title = inline_match.group(1).strip()
            org = inline_match.group(2).strip()
            loc = inline_match.group(3).strip() if inline_match.group(3) else None
            start_d = inline_match.group(4).strip()
            end_d = inline_match.group(5).strip()
            is_curr = end_d.lower() in ("present", "current")
            current_entry = {
                "title": title,
                "organization": org,
                "location": loc,
                "start_date": start_d,
                "end_date": end_d,
                "duration": f"{start_d} – {end_d}",
                "is_current": is_curr,
                "source_evidence": line.strip(),
                "confidence": "EXTRACTED_EXACT",
                "responsibilities": [],
                "achievements": [],
            }
            entries.append(current_entry)
            i += 1
        elif date_match and i + 2 < len(lines) and not re.match(bullet_re, lines[i + 1]):
            start_d = date_match.group(1).strip()
            end_d = date_match.group(2).strip()
            is_curr = end_d.lower() in ("present", "current")
            org = lines[i + 1].strip()
            title = lines[i + 2].strip()
            current_entry = {
                "title": title,
                "organization": org,
                "location": None,
                "start_date": start_d,
                "end_date": end_d,
                "duration": f"{start_d} – {end_d}",
                "is_current": is_curr,
                "source_evidence": f"{line.strip()} | {org} | {title}",
                "confidence": "EXTRACTED_EXACT",
                "responsibilities": [],
                "achievements": [],
            }
            entries.append(current_entry)
            i += 3
        elif current_entry:
            is_bullet = bool(re.match(bullet_re, line))
            clean = re.sub(bullet_re, "", line).strip()
            if clean:
                if is_bullet or not current_entry["responsibilities"]:
                    current_entry["responsibilities"].append(clean)
                else:
                    current_entry["responsibilities"][-1] += " " + clean
            i += 1
        else:
            i += 1

    for entry in entries:
        for resp in entry["responsibilities"]:
            if re.search(
                r"(?:\d+%\s*|\d+\+\s*|\d+M\+\s*|ROC-AUC|₹|\$|\b(?:increased|reduced|lowered|lowering|cutting|cut|driving|driven|improved|improving|expanded|achieved|automating)\b)",
                resp,
                re.IGNORECASE,
            ):
                entry["achievements"].append(resp)

    return entries


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
        experience = extract_experience_entries(resume_text)
        languages = extract_languages(resume_text)
        projects = extract_projects(resume_text)
        certifications, publications = extract_certifications_and_publications(resume_text)
        candidate = extract_candidate_info(resume_text)
        skill_categories = categorize_skills(tech_skills, soft_skills)

        # Baseline readiness based on resume completeness breakdown
        has_contact = bool(
            re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", resume_text)
            or re.search(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", resume_text)
        )
        contact_score = 10.0 if has_contact else 0.0
        education_score = 25.0 if education else 0.0
        exp_score = 25.0 if exp_years > 0 or experience else 0.0
        tech_score = min(len(tech_skills) * 5.0, 20.0)
        soft_lang_score = min(
            len(soft_skills) * 2.5
            + len(languages) * 2.5
            + len(projects) * 5.0
            + len(certifications) * 5.0
            + len(publications) * 5.0,
            20.0,
        )

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
                "work experience history, technical/soft skills, languages, projects, certifications, and publications). "
                "Resume completeness measures documentation coverage, not guaranteed job readiness or hiring decisions."
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
        if exp_years == 0 and not experience:
            recommendations.append(
                "Highlight academic projects, hackathons, or internships to demonstrate practical experience."
            )
        if not languages:
            recommendations.append(
                "List spoken and written languages with proficiency levels to enhance global profile visibility."
            )
        if not projects:
            recommendations.append(
                "Highlight personal or open-source projects with measurable outcomes to demonstrate hands-on application."
            )
        if not certifications:
            recommendations.append(
                "Consider industry certifications (e.g., AWS, Azure, GCP) to validate core competencies."
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
            projects=projects,
            certifications=certifications,
            publications=publications,
            candidate=candidate,
            experience=experience,
            skill_categories=skill_categories,
            completeness_score=readiness_score,
            completeness_breakdown=breakdown,
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
            projects=base_result.projects,
            certifications=base_result.certifications,
            publications=base_result.publications,
            candidate=base_result.candidate,
            experience=base_result.experience,
            skill_categories=base_result.skill_categories,
            completeness_score=base_result.completeness_score,
            completeness_breakdown=base_result.completeness_breakdown,
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
