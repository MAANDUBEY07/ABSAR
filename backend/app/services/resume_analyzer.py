"""Extract lexical resume claims with quotes and character offsets, without profile mutation."""

import re

SKILLS = (
    "python",
    "javascript",
    "typescript",
    "java",
    "sql",
    "react",
    "docker",
    "git",
    "aws",
    "excel",
    "machine learning",
    "communication",
    "leadership",
    "c++",
    "fastapi",
    "postgresql",
)


def claims(text):
    found = []
    for skill in SKILLS:
        for match in re.finditer(r"(?<!\w)" + re.escape(skill) + r"(?!\w)", text, re.I):
            prefix = text[max(0, match.start() - 45) : match.start()]
            if re.search(r"(?:no|not|without|lack(?:ing)?|never)\s+(?:\w+\s+){0,3}$", prefix, re.I):
                continue
            found.append(
                dict(
                    skill=skill,
                    quote=match.group(),
                    start=match.start(),
                    end=match.end(),
                    source="RESUME_CLAIM",
                )
            )
    return found


def analyze_resume(text, owner_id, document_id):
    from app.models.resume import ResumeAnalysis

    evidence = claims(text)
    return ResumeAnalysis(
        owner_id=owner_id,
        document_id=document_id,
        skills=sorted({claim["skill"] for claim in evidence}),
        evidence=evidence,
        disclaimer="Resume claims; confirm explicitly through profile updates",
    ).model_dump(mode="json")
