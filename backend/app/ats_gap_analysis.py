from __future__ import annotations

from .ats_evidence import TermAssessment
from .ats_normalization import best_match_type, is_strong_match_type
from .ats_role_matching import RoleMatchResult
from .job_description import JobDescriptionAnalysis
from .resume_parser import ResumeAnalysis


LOW_SIGNAL_TERMS = {
    "actionable",
    "ai/ml",
    "analytical",
    "analyze",
    "architecture",
    "backend",
    "business",
    "cloud",
    "comfortable",
    "evaluate",
    "qualification",
    "qualifications",
    "strong",
}


def build_gap_analysis(
    job: JobDescriptionAnalysis,
    resume: ResumeAnalysis,
    assessments: list[TermAssessment],
    role_match: RoleMatchResult,
) -> dict[str, object]:
    assessment_map = {item.term: item for item in assessments}
    missing_required = _missing_terms(job.required_skills, assessment_map, required=True)
    missing_preferred = _missing_terms([*job.preferred_skills, *job.tools], assessment_map, required=False)
    missing_role_signals = [
        {"signal": signal, "details": signal, "severity": "high" if index == 0 else "medium"}
        for index, signal in enumerate(role_match.missing_signals)
    ]
    missing_education = _missing_education(job, resume, assessments)
    critical_gaps = _critical_gaps(job, resume, missing_required, missing_role_signals, missing_education)

    missing_keywords = _legacy_missing_keywords(assessments, job)
    return {
        "critical_gaps": critical_gaps,
        "missing_required_skills": missing_required,
        "missing_preferred_skills": missing_preferred,
        "missing_role_signals": missing_role_signals,
        "missing_education_certifications": missing_education,
        "missing_keywords": missing_keywords,
    }


def _missing_terms(terms: list[str], assessment_map: dict[str, TermAssessment], *, required: bool) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for term in terms:
        if term.lower() in seen:
            continue
        seen.add(term.lower())
        assessment = assessment_map.get(term)
        if assessment and assessment.is_matched and (not required or is_strong_match_type(assessment.match_type)):
            continue
        if assessment and assessment.is_matched and assessment.match_type == "related":
            details = f"{term} has only weak related evidence, not a clear direct match."
        else:
            details = f"{term} is not clearly supported in the resume."
        output.append(
            {
                "keyword": term,
                "importance": "high" if required else "medium",
                "category": assessment.category if assessment else "keyword",
                "details": details,
            }
        )
    return output[:12]


def _missing_education(job: JobDescriptionAnalysis, resume: ResumeAnalysis, assessments: list[TermAssessment]) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    education_text = resume.section_text.get("education", "")
    certification_text = resume.section_text.get("certifications", "")
    for requirement in job.degree_requirements:
        if not best_match_type(requirement, education_text + " " + resume.section_text.get("summary", "")):
            gaps.append(
                {
                    "keyword": requirement,
                    "importance": "high",
                    "category": "education",
                    "details": f"The JD references {requirement}, but the education section does not clearly show it.",
                }
            )
    for certification in job.certifications:
        assessment = next((item for item in assessments if item.term == certification), None)
        if not certification_text or not (assessment and assessment.is_matched):
            gaps.append(
                {
                    "keyword": certification,
                    "importance": "high",
                    "category": "certification",
                    "details": f"The JD references {certification}, but the resume does not clearly list it.",
                }
            )
    return gaps[:8]


def _critical_gaps(
    job: JobDescriptionAnalysis,
    resume: ResumeAnalysis,
    missing_required: list[dict[str, str]],
    missing_role_signals: list[dict[str, str]],
    missing_education: list[dict[str, str]],
) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    for item in missing_required:
        if item["category"] != "hard_skill":
            continue
        gaps.append(
            {
                "title": f"Missing required skill: {item['keyword']}",
                "details": item["details"],
                "impact": "Required skill gaps can materially reduce recruiter confidence and ATS ranking.",
            }
        )
    if job.years_required and resume.experience_years + 0.5 < job.years_required:
        gaps.append(
            {
                "title": "Experience level below stated requirement",
                "details": f"The role asks for about {job.years_required}+ years, while the resume shows roughly {resume.experience_years} years.",
                "impact": "This can reduce shortlist likelihood even when some skills are relevant.",
            }
        )
    for signal in missing_role_signals[:1]:
        gaps.append(
            {
                "title": "Core role alignment is weak",
                "details": signal["details"],
                "impact": "Recruiters may not immediately read the resume as aligned to the target role family.",
            }
        )
    for item in missing_education[:2]:
        gaps.append(
            {
                "title": f"Missing education/certification signal: {item['keyword']}",
                "details": item["details"],
                "impact": "If this is a hard requirement, it can become a screen-out criterion.",
            }
        )
    return gaps[:8]


def _legacy_missing_keywords(assessments: list[TermAssessment], job: JobDescriptionAnalysis) -> list[dict[str, str]]:
    missing_keywords: list[dict[str, str]] = []
    high_priority_terms = set(job.required_skills + job.certifications)
    medium_priority_terms = set(job.preferred_skills + [term for term in job.tools if term not in high_priority_terms])
    for item in assessments:
        if item.is_matched and is_strong_match_type(item.match_type):
            continue
        if item.term in high_priority_terms:
            importance = "high"
        elif item.term in medium_priority_terms:
            importance = "medium"
        else:
            importance = "low"
        if importance == "low" and item.category == "keyword" and item.term.lower() in LOW_SIGNAL_TERMS:
            continue
        missing_keywords.append(
            {
                "keyword": item.term,
                "importance": importance,
                "category": item.category,
                "details": _missing_keyword_reason(item.term, importance, item.match_type),
            }
        )
    missing_keywords.sort(key=lambda entry: (_importance_order(entry["importance"]), entry["keyword"]))
    return missing_keywords[:18]


def _missing_keyword_reason(term: str, importance: str, match_type: str | None) -> str:
    if match_type == "related":
        return f"{term} has only related evidence; add a direct truthful mention if you have used it."
    if importance == "high":
        return f"{term} appears to be a required qualification and is not clearly supported in the resume."
    if importance == "medium":
        return f"{term} is part of the preferred or tool stack language in the job posting."
    return f"{term} appears in the job description and could improve contextual keyword coverage."


def _importance_order(importance: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}[importance]
