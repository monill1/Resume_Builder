from __future__ import annotations

import re
from dataclasses import dataclass

from .ats_normalization import normalize_text, similarity_ratio, tokenize
from .job_description import JobDescriptionAnalysis
from .resume_parser import ResumeAnalysis


ROLE_FAMILIES = {
    "backend_engineer": {
        "backend engineer",
        "backend developer",
        "python backend engineer",
        "api developer",
        "server-side engineer",
        "software engineer backend",
    },
    "frontend_engineer": {"frontend engineer", "frontend developer", "react developer", "ui engineer", "web developer"},
    "full_stack_developer": {"full stack developer", "full-stack engineer", "full stack engineer", "mern developer"},
    "data_analyst": {"data analyst", "business intelligence analyst", "bi analyst", "analytics analyst"},
    "data_scientist": {"data scientist", "decision scientist", "research scientist data"},
    "machine_learning_engineer": {"machine learning engineer", "ml engineer", "ai/ml engineer", "modeling engineer"},
    "ai_engineer": {"ai engineer", "generative ai engineer", "llm engineer", "prompt engineer"},
    "business_analyst": {"business analyst", "product analyst", "operations analyst", "systems analyst"},
    "devops_engineer": {"devops engineer", "site reliability engineer", "sre", "platform engineer", "cloud engineer"},
}

RELATED_ROLE_FAMILIES = {
    "backend_engineer": {"full_stack_developer", "devops_engineer"},
    "frontend_engineer": {"full_stack_developer"},
    "full_stack_developer": {"backend_engineer", "frontend_engineer"},
    "data_analyst": {"business_analyst", "data_scientist"},
    "business_analyst": {"data_analyst"},
    "data_scientist": {"machine_learning_engineer", "data_analyst", "ai_engineer"},
    "machine_learning_engineer": {"ai_engineer", "data_scientist", "backend_engineer"},
    "ai_engineer": {"machine_learning_engineer", "data_scientist"},
    "devops_engineer": {"backend_engineer"},
}

SENIORITY_PATTERNS = {
    "intern": re.compile(r"\b(intern|internship|trainee)\b", re.IGNORECASE),
    "junior": re.compile(r"\b(junior|jr\.?|entry level|associate)\b", re.IGNORECASE),
    "mid": re.compile(r"\b(mid|software engineer|developer|analyst|engineer)\b", re.IGNORECASE),
    "senior": re.compile(r"\b(senior|sr\.?|lead|principal|staff|manager)\b", re.IGNORECASE),
}
SENIORITY_RANK = {"intern": 0, "junior": 1, "mid": 2, "senior": 3}


@dataclass(frozen=True)
class RoleMatchResult:
    score: int
    job_family: str | None
    resume_family: str | None
    title_similarity: float
    family_similarity: float
    seniority_similarity: float
    missing_signals: list[str]


def match_role(job: JobDescriptionAnalysis, resume: ResumeAnalysis) -> RoleMatchResult:
    job_family = detect_role_family(" ".join([job.title, job.source.description, job.source.text[:1200]]))
    resume_title_text = " ".join(resume.experience_titles + [resume.section_text.get("summary", "")])
    resume_family = detect_role_family(resume_title_text)
    title_similarity = max((similarity_ratio(job.title, title) for title in resume.experience_titles), default=0.0)
    if normalize_text(job.title) in normalize_text(resume_title_text):
        title_similarity = max(title_similarity, 1.0)

    family_similarity = _family_similarity(job_family, resume_family)
    seniority_similarity = seniority_alignment(job.title, resume_title_text, job.years_required, resume.experience_years)
    token_overlap = _token_overlap(job.title, resume_title_text)
    score = round(100 * (0.36 * title_similarity + 0.34 * family_similarity + 0.18 * seniority_similarity + 0.12 * token_overlap))

    missing_signals: list[str] = []
    if family_similarity < 0.5:
        missing_signals.append(f"Resume titles do not strongly signal the {human_role_family(job_family)} role family.")
    if seniority_similarity < 0.65:
        missing_signals.append("Resume seniority or years of experience appear below the job requirement.")
    if title_similarity < 0.35 and token_overlap < 0.35:
        missing_signals.append("Target role title language is weak or absent in resume titles/summary.")

    return RoleMatchResult(
        score=max(0, min(100, score)),
        job_family=job_family,
        resume_family=resume_family,
        title_similarity=round(title_similarity, 2),
        family_similarity=round(family_similarity, 2),
        seniority_similarity=round(seniority_similarity, 2),
        missing_signals=missing_signals,
    )


def responsibility_alignment(job: JobDescriptionAnalysis, resume: ResumeAnalysis) -> int:
    phrases = job.responsibility_phrases + job.action_phrases
    if not phrases:
        return 78
    resume_text = " ".join([resume.section_text.get("experience", ""), resume.section_text.get("projects", ""), resume.section_text.get("summary", "")])
    phrase_scores: list[float] = []
    resume_tokens = set(tokenize(resume_text))
    for phrase in phrases[:8]:
        tokens = {token for token in tokenize(phrase) if len(token) > 3}
        if not tokens:
            continue
        overlap = len(tokens & resume_tokens) / len(tokens)
        phrase_scores.append(max(overlap, similarity_ratio(phrase, resume_text[:600]) * 0.6))
    if not phrase_scores:
        return 70
    return round(100 * min(1.0, sum(phrase_scores) / len(phrase_scores)))


def years_alignment(required_years: int | None, resume_years: float) -> int:
    if not required_years:
        return 82
    if resume_years >= required_years:
        return 100
    if resume_years + 0.5 >= required_years:
        return 82
    return round(100 * max(0.22, resume_years / required_years))


def seniority_alignment(job_title: str, resume_title_text: str, required_years: int | None, resume_years: float) -> float:
    job_level = _seniority_level(job_title, required_years)
    resume_level = _seniority_level(resume_title_text, round(resume_years) if resume_years else None)
    gap = SENIORITY_RANK[job_level] - SENIORITY_RANK[resume_level]
    if gap <= 0:
        return 1.0
    if gap == 1:
        return 0.74
    if gap == 2:
        return 0.48
    return 0.24


def detect_role_family(text: str) -> str | None:
    normalized = normalize_text(text)
    best_family: str | None = None
    best_score = 0.0
    for family, aliases in ROLE_FAMILIES.items():
        for alias in aliases:
            alias_norm = normalize_text(alias)
            if alias_norm in normalized:
                return family
            score = similarity_ratio(alias, normalized)
            overlap = _token_overlap(alias, normalized)
            combined = max(score, overlap)
            if combined > best_score:
                best_score = combined
                best_family = family
    return best_family if best_score >= 0.54 else None


def human_role_family(family: str | None) -> str:
    if not family:
        return "target"
    return family.replace("_", " ")


def _family_similarity(job_family: str | None, resume_family: str | None) -> float:
    if not job_family or not resume_family:
        return 0.45 if job_family or resume_family else 0.55
    if job_family == resume_family:
        return 1.0
    if resume_family in RELATED_ROLE_FAMILIES.get(job_family, set()):
        return 0.68
    return 0.28


def _seniority_level(text: str, years: int | None) -> str:
    for level in ("intern", "junior", "senior"):
        if SENIORITY_PATTERNS[level].search(text or ""):
            return level
    if years is not None:
        if years < 1:
            return "intern"
        if years < 3:
            return "junior"
        if years >= 6:
            return "senior"
    return "mid"


def _token_overlap(left: str, right: str) -> float:
    left_tokens = {token for token in tokenize(left) if len(token) > 2}
    right_tokens = {token for token in tokenize(right) if len(token) > 2}
    return len(left_tokens & right_tokens) / len(left_tokens) if left_tokens else 0.0
