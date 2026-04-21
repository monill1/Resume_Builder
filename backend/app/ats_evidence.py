from __future__ import annotations

import re
from dataclasses import dataclass

from .ats_config import ATS_SCORING_CONFIG
from .ats_normalization import (
    best_match_type,
    classify_term,
    dedupe_preserve_order,
    find_evidence_snippets,
    is_strong_match_type,
    match_strength,
    skill_category_for,
)
from .job_description import JobDescriptionAnalysis
from .resume_parser import ResumeAnalysis


ACTION_WORD_RE = re.compile(
    r"\b(built|designed|developed|implemented|created|improved|optimized|led|analyzed|shipped|deployed|"
    r"partnered|owned|delivered|automated|reduced|increased|launched|maintained|migrated|architected)\b",
    re.IGNORECASE,
)
METRIC_RE = re.compile(r"\b\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?(?:x|k|m|b)\b|\b\d+\b", re.IGNORECASE)
CONTEXT_RE = re.compile(
    r"\b(api|service|pipeline|dashboard|model|workflow|customer|user|business|product|backend|frontend|"
    r"database|deployment|analytics|reporting|latency|accuracy|revenue|cost|performance|scale)\b",
    re.IGNORECASE,
)
SCOPE_RE = re.compile(
    r"\b(owned|led|end-to-end|cross-functional|production|scalable|monthly|weekly|enterprise|stakeholder|"
    r"team|platform|architecture|roadmap|client|customer-facing)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EvidenceHit:
    section: str
    snippet: str
    match_type: str
    quality_score: int
    tier: int
    signals: list[str]


@dataclass(frozen=True)
class TermAssessment:
    term: str
    importance: str
    category: str
    skill_category: str
    match_type: str | None
    sections: list[str]
    evidence: list[str]
    evidence_hits: list[EvidenceHit]
    occurrence_count: int
    evidence_tier: int
    evidence_quality: int

    @property
    def is_matched(self) -> bool:
        return bool(self.match_type)

    @property
    def has_strong_match(self) -> bool:
        return is_strong_match_type(self.match_type)

    @property
    def is_skills_only(self) -> bool:
        return self.sections == ["skills"]


def build_term_assessments(job: JobDescriptionAnalysis, resume: ResumeAnalysis) -> list[TermAssessment]:
    importance_by_term: dict[str, str] = {}
    ordered_terms: list[str] = []
    for term in job.required_skills:
        importance_by_term[term] = "high"
        ordered_terms.append(term)
    for term in job.preferred_skills:
        importance_by_term.setdefault(term, "medium")
        ordered_terms.append(term)
    for term in job.tools:
        importance_by_term.setdefault(term, "medium")
        ordered_terms.append(term)
    for term in job.industry_keywords:
        importance_by_term.setdefault(term, "low")
        ordered_terms.append(term)
    for term in job.certifications:
        importance_by_term.setdefault(term, "high")
        ordered_terms.append(term)

    assessments: list[TermAssessment] = []
    all_text = "\n".join(resume.section_text.values())
    for term in dedupe_preserve_order(ordered_terms):
        hits = find_term_evidence(term, resume)
        best_hit = max(
            hits,
            key=lambda hit: (1 if is_strong_match_type(hit.match_type) else 0, hit.tier, hit.quality_score, match_strength(hit.match_type)),
            default=None,
        )
        sections = dedupe_preserve_order(hit.section for hit in hits)
        snippets = dedupe_preserve_order(hit.snippet for hit in hits if hit.snippet)[:3]
        assessments.append(
            TermAssessment(
                term=term,
                importance=importance_by_term[term],
                category=classify_term(term),
                skill_category=skill_category_for(term),
                match_type=best_hit.match_type if best_hit else None,
                sections=sections,
                evidence=snippets,
                evidence_hits=hits[:6],
                occurrence_count=count_occurrences(term, all_text),
                evidence_tier=best_hit.tier if best_hit else 0,
                evidence_quality=best_hit.quality_score if best_hit else 0,
            )
        )
    return assessments


def find_term_evidence(term: str, resume: ResumeAnalysis) -> list[EvidenceHit]:
    hits: list[EvidenceHit] = []
    for section, lines in resume.section_lines.items():
        section_text = "\n".join(lines)
        section_match = best_match_type(term, section_text)
        if not section_match:
            continue
        snippets = find_evidence_snippets(section_text, term, max_hits=3) or [section_text[:180]]
        for snippet in snippets:
            match_type = best_match_type(term, snippet) or section_match
            quality, signals = score_bullet_quality(snippet, has_term=True)
            tier = evidence_tier(section, quality, snippet)
            hits.append(
                EvidenceHit(
                    section=section,
                    snippet=snippet,
                    match_type=match_type,
                    quality_score=quality,
                    tier=tier,
                    signals=signals,
                )
            )
    return sorted(
        hits,
        key=lambda hit: (1 if is_strong_match_type(hit.match_type) else 0, hit.tier, hit.quality_score, match_strength(hit.match_type)),
        reverse=True,
    )


def score_bullet_quality(text: str, *, has_term: bool = False) -> tuple[int, list[str]]:
    config = ATS_SCORING_CONFIG["evidence"]
    signals: list[str] = []
    score = 0.0
    if ACTION_WORD_RE.search(text):
        score += config["action_weight"]
        signals.append("action")
    if has_term or _has_tool_like_token(text):
        score += config["tool_weight"]
        signals.append("tool")
    if CONTEXT_RE.search(text):
        score += config["context_weight"]
        signals.append("context")
    if METRIC_RE.search(text):
        score += config["metric_weight"]
        signals.append("metric")
    if SCOPE_RE.search(text):
        score += config["scope_weight"]
        signals.append("scope")
    if len(text.split()) >= 10:
        score = min(1.0, score + 0.05)
    return round(score * 100), signals


def evidence_tier(section: str, quality_score: int, snippet: str) -> int:
    if section == "skills":
        return 1
    if section == "projects":
        return 4 if _is_high_quality_evidence(quality_score, snippet) else 2
    if section == "experience":
        return 4 if _is_high_quality_evidence(quality_score, snippet) else 3
    if section in {"summary", "certifications", "education"}:
        return 2 if quality_score >= 55 else 1
    return 1


def average_bullet_quality(lines: list[str]) -> int:
    candidates = [line for line in lines if len(line.split()) >= 4]
    if not candidates:
        return 0
    return round(sum(score_bullet_quality(line)[0] for line in candidates) / len(candidates))


def count_occurrences(term: str, text: str) -> int:
    from .ats_normalization import aliases_for, exact_phrase_present, normalize_text

    count = 0
    normalized_text = normalize_text(text)
    for alias in aliases_for(term):
        escaped = re.escape(normalize_text(alias))
        if not escaped:
            continue
        count = max(count, len(re.findall(rf"(?<!\w){escaped}(?!\w)", normalized_text)))
    if not count and any(exact_phrase_present(alias, text) for alias in aliases_for(term)):
        return 1
    return count


def _is_high_quality_evidence(quality_score: int, snippet: str) -> bool:
    return quality_score >= ATS_SCORING_CONFIG["evidence"]["tier_4_min"] and bool(ACTION_WORD_RE.search(snippet) and METRIC_RE.search(snippet))


def _has_tool_like_token(text: str) -> bool:
    return bool(re.search(r"\b[A-Z][A-Za-z0-9+#./-]{1,}\b|[A-Za-z]+(?:API|SQL|DB)\b", text))
