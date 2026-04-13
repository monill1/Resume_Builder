from __future__ import annotations

import re
from dataclasses import dataclass

from .ats_config import ATS_SCORING_CONFIG, score_label
from .ats_normalization import (
    aliases_for,
    best_match_type,
    classify_term,
    dedupe_preserve_order,
    exact_phrase_present,
    find_evidence_snippets,
    normalize_text,
    similarity_ratio,
)
from .ats_recommendations import build_explanation_panel, suggestion_for_formatting, suggestion_for_missing_keyword
from .job_description import JobDescriptionAnalysis
from .resume_parser import ResumeAnalysis


ACTION_WORD_RE = re.compile(r"\b(built|designed|developed|implemented|created|improved|optimized|led|analyzed|shipped|deployed|partnered)\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"\b\d")
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


@dataclass(frozen=True)
class TermAssessment:
    term: str
    importance: str
    category: str
    match_type: str | None
    sections: list[str]
    evidence: list[str]
    occurrence_count: int


def score_resume(job: JobDescriptionAnalysis, resume: ResumeAnalysis) -> dict[str, object]:
    config = ATS_SCORING_CONFIG
    assessments = _build_term_assessments(job, resume)

    # Each section score stays independently explainable so the UI can surface
    # exactly which ATS factor is lowering the final score.
    section_scores = {
        "skills_match": _score_skills(job, assessments),
        "experience_relevance": _score_experience(job, resume, assessments),
        "keyword_coverage": _score_keyword_coverage(assessments),
        "education_certifications": _score_education(job, resume, assessments),
    }

    formatting_score, parsing_confidence, formatting_issues = _score_formatting(job, resume)
    completeness_score = _score_completeness(job, resume, assessments)
    section_scores["formatting_parseability"] = formatting_score
    section_scores["completeness"] = completeness_score

    overall_raw = round(
        sum(config["weights"][key] * value for key, value in section_scores.items())
    )
    overall_score, score_cap_applied, score_cap_reason = _apply_parsing_cap(overall_raw, parsing_confidence)

    matched_keywords, missing_keywords = _build_keyword_outputs(assessments, job)
    critical_gaps = _build_critical_gaps(job, resume, assessments)
    suggestions = _build_suggestions(job, section_scores, missing_keywords, formatting_issues, critical_gaps)
    comparison_view = _build_comparison_view(job, assessments)
    strengths, risks = _build_explanation_points(section_scores, matched_keywords, missing_keywords, formatting_issues, critical_gaps)
    explanation_panel = build_explanation_panel(
        overall_score=overall_score,
        parsing_confidence=parsing_confidence,
        strengths=strengths,
        risks=risks,
    )

    return {
        "overall_score": overall_score,
        "confidence_label": score_label(overall_score),
        "parsing_confidence": round(parsing_confidence, 2),
        "score_cap_applied": score_cap_applied,
        "score_cap_reason": score_cap_reason,
        "summary": explanation_panel["summary"],
        "section_scores": {key: int(value) for key, value in section_scores.items()},
        "missing_keywords": missing_keywords,
        "matched_keywords": matched_keywords,
        "formatting_issues": formatting_issues,
        "critical_gaps": critical_gaps,
        "improvement_suggestions": suggestions,
        "parse_preview": resume.parse_preview,
        "comparison_view": comparison_view,
        "explanation_panel": explanation_panel,
    }


def _build_term_assessments(job: JobDescriptionAnalysis, resume: ResumeAnalysis) -> list[TermAssessment]:
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
    for term in dedupe_preserve_order(ordered_terms):
        sections: list[str] = []
        evidence: list[str] = []
        best_match: str | None = None

        # We collect section-level evidence first, then score it later with
        # context bonuses so real bullet-point usage beats keyword-only lists.
        for section, text in resume.section_text.items():
            match_type = best_match_type(term, text)
            if not match_type:
                continue
            sections.append(section)
            evidence.extend(find_evidence_snippets(text, term, max_hits=2))
            if best_match != "exact":
                best_match = match_type
        assessments.append(
            TermAssessment(
                term=term,
                importance=importance_by_term[term],
                category=classify_term(term),
                match_type=best_match,
                sections=dedupe_preserve_order(sections),
                evidence=dedupe_preserve_order(evidence)[:3],
                occurrence_count=_count_occurrences(term, "\n".join(resume.section_text.values())),
            )
        )
    return assessments


def _score_skills(job: JobDescriptionAnalysis, assessments: list[TermAssessment]) -> int:
    config = ATS_SCORING_CONFIG["skills"]
    required_terms = set(job.required_skills)
    preferred_terms = set(job.preferred_skills) or {term for term in job.tools if term not in required_terms}
    required_score = _weighted_term_average([item for item in assessments if item.term in required_terms], config)
    preferred_score = _weighted_term_average([item for item in assessments if item.term in preferred_terms], config)
    total = (config["required_weight"] * required_score) + (config["preferred_weight"] * preferred_score)

    missing_required_hard_skills = sum(
        1
        for item in assessments
        if item.term in required_terms and item.category == "hard_skill" and not item.match_type
    )
    total -= min(18, missing_required_hard_skills * config["critical_required_skill_penalty"])
    return _clamp_score(round(total))


def _weighted_term_average(assessments: list[TermAssessment], config: dict[str, object]) -> float:
    if not assessments:
        return 82.0
    weighted_total = 0.0
    total_weight = 0.0
    for item in assessments:
        category_weight = config["hard_skill_weight"] if item.category == "hard_skill" else config["soft_skill_weight"]
        weighted_total += _term_score(item, config) * category_weight
        total_weight += category_weight
    return (weighted_total / total_weight) if total_weight else 0.0


def _term_score(item: TermAssessment, config: dict[str, object]) -> float:
    if item.match_type == "exact":
        base = config["exact_match_score"]
    elif item.match_type == "semantic":
        base = config["semantic_match_score"]
    else:
        return 0.0

    best_section_bonus = max(config["section_bonus"].get(section, 0.6) for section in item.sections)
    context_bonus_key = "list_only"
    if any(NUMBER_RE.search(snippet) for snippet in item.evidence):
        context_bonus_key = "measurable_bullet"
    elif any(ACTION_WORD_RE.search(snippet) for snippet in item.evidence):
        context_bonus_key = "action_or_achievement"
    score = 100 * base * best_section_bonus * config["context_bonus"][context_bonus_key]
    return min(100.0, score)


def _score_experience(job: JobDescriptionAnalysis, resume: ResumeAnalysis, assessments: list[TermAssessment]) -> int:
    config = ATS_SCORING_CONFIG["experience"]
    title_alignment = _title_alignment(job.title, resume)
    domain_alignment = _domain_alignment(job, assessments)
    years_alignment = _years_alignment(job.years_required, resume.experience_years)
    evidence_alignment = _experience_evidence_alignment(job, assessments)
    score = 100 * (
        config["title_alignment_weight"] * title_alignment
        + config["domain_weight"] * domain_alignment
        + config["years_weight"] * years_alignment
        + config["evidence_weight"] * evidence_alignment
    )
    return _clamp_score(round(score))


def _title_alignment(job_title: str, resume: ResumeAnalysis) -> float:
    title_candidates = [job_title, *resume.experience_titles]
    similarity = max((similarity_ratio(job_title, candidate) for candidate in title_candidates), default=0.0)
    tokens = {token for token in normalize_text(job_title).split() if len(token) > 2}
    resume_tokens = {token for token in normalize_text(" ".join(resume.experience_titles)).split() if len(token) > 2}
    overlap = len(tokens & resume_tokens) / len(tokens) if tokens else 0.0
    return min(1.0, max(similarity, overlap, similarity * 0.8 + overlap * 0.2))


def _domain_alignment(job: JobDescriptionAnalysis, assessments: list[TermAssessment]) -> float:
    domain_terms = [item for item in assessments if item.term in job.industry_keywords]
    if not domain_terms:
        return 0.84
    matched = sum(1 for item in domain_terms if item.match_type)
    return matched / len(domain_terms)


def _years_alignment(required_years: int | None, resume_years: float) -> float:
    if not required_years:
        return 0.86
    if resume_years >= required_years:
        return 1.0
    if resume_years + 0.5 >= required_years:
        return 0.82
    return max(0.22, resume_years / required_years)


def _experience_evidence_alignment(job: JobDescriptionAnalysis, assessments: list[TermAssessment]) -> float:
    relevant = [item for item in assessments if item.term in set(job.required_skills + job.tools)]
    if not relevant:
        return 0.84
    matched = 0.0
    for item in relevant:
        if item.match_type == "exact" and any(section in {"experience", "projects"} for section in item.sections):
            matched += 1.0
        elif item.match_type and any(section in {"experience", "projects"} for section in item.sections):
            matched += 0.75
        elif item.match_type:
            matched += 0.4
    return min(1.0, matched / len(relevant))


def _score_keyword_coverage(assessments: list[TermAssessment]) -> int:
    config = ATS_SCORING_CONFIG["keyword_coverage"]
    if not assessments:
        return 0

    weighted_total = 0.0
    total_weight = 0.0
    penalty = 0
    for item in assessments:
        importance_weight = {"high": 1.0, "medium": 0.68, "low": 0.42}[item.importance]
        total_weight += importance_weight
        if not item.match_type:
            continue
        match_score = config["exact_match_score"] if item.match_type == "exact" else config["semantic_match_score"]
        section_bonus = max(config["section_weights"].get(section, 0.5) for section in item.sections)
        weighted_total += importance_weight * min(1.0, match_score * section_bonus)

        # Repetition gets capped and then penalized so obvious stuffing cannot
        # inflate the score above natural, contextual evidence.
        if item.occurrence_count > config["stuffing_repeat_threshold"]:
            penalty += (item.occurrence_count - config["stuffing_repeat_threshold"]) * config["stuffing_penalty_per_extra"]
        if item.sections == ["skills"] and item.importance in {"high", "medium"}:
            penalty += config["skills_only_penalty"]

    score = 100 * (weighted_total / total_weight) if total_weight else 0.0
    return _clamp_score(round(score - penalty))


def _score_education(job: JobDescriptionAnalysis, resume: ResumeAnalysis, assessments: list[TermAssessment]) -> int:
    config = ATS_SCORING_CONFIG["education"]
    education_text = resume.section_text["education"]
    certifications_text = resume.section_text["certifications"]
    degree_score = 0.84 if education_text else 0.45
    if job.degree_requirements:
        degree_matches = [
            best_match_type(requirement, education_text) or best_match_type(requirement, resume.section_text["summary"])
            for requirement in job.degree_requirements
        ]
        degree_score = 1.0 if any(match == "exact" for match in degree_matches) else 0.65 if any(degree_matches) else 0.0

    cert_score = 0.82 if certifications_text else 0.7
    if job.certifications:
        cert_matches = [
            item for item in assessments if item.term in job.certifications and item.match_type
        ]
        cert_score = 1.0 if cert_matches else 0.0

    location_score = 1.0
    if job.location_requirements:
        location_score = 1.0 if any(best_match_type(term, resume.section_text["summary"] + " " + resume.parse_preview) for term in job.location_requirements) else 0.0

    auth_score = 1.0
    if job.authorization_requirements:
        auth_score = 1.0 if any(best_match_type(term, resume.parse_preview) for term in job.authorization_requirements) else 0.0

    if not (job.degree_requirements or job.certifications or job.location_requirements or job.authorization_requirements):
        return _clamp_score(round(config["baseline_without_explicit_requirement"]))

    score = 100 * (
        config["degree_weight"] * degree_score
        + config["certification_weight"] * cert_score
        + config["location_weight"] * location_score
        + config["authorization_weight"] * auth_score
    )
    return _clamp_score(round(score))


def _score_formatting(job: JobDescriptionAnalysis, resume: ResumeAnalysis) -> tuple[int, float, list[dict[str, str]]]:
    config = ATS_SCORING_CONFIG["formatting"]
    score = config["base_score"]
    issues: list[dict[str, str]] = []

    if not all((resume.contact_signals["email"], resume.contact_signals["phone"], resume.contact_signals["location"])):
        score -= config["missing_contact_penalty"]
        issues.append(
            {
                "severity": "high",
                "issue": "Missing contact details",
                "details": "ATS systems and recruiters expect email, phone, and location in clear text.",
                "recommendation": "Add missing contact details in the top section using plain text.",
            }
        )
    if len(resume.date_formats) > 1:
        score -= config["date_inconsistency_penalty"]
        issues.append(
            {
                "severity": "medium",
                "issue": "Inconsistent date formatting",
                "details": "Mixed date styles make timeline parsing less reliable.",
                "recommendation": "Use one date style consistently, such as `2024 - 2025` or `Jan 2024 - Mar 2025` throughout.",
            }
        )
    if resume.parse_warnings:
        unusual_order = any("Section order" in warning for warning in resume.parse_warnings)
        if unusual_order:
            score -= config["unclear_section_order_penalty"]
            issues.append(
                {
                    "severity": "medium",
                    "issue": "Section flow is less standard",
                    "details": "ATS systems parse most reliably when summary, skills, and experience appear in a predictable order.",
                    "recommendation": "Move Summary, Skills, and Experience near the top in a straightforward top-to-bottom flow.",
                }
            )
        low_preview = any("Plain-text parse preview is short" in warning for warning in resume.parse_warnings)
        if low_preview:
            score -= config["low_parse_preview_penalty"]
            issues.append(
                {
                    "severity": "medium",
                    "issue": "Low parseable text volume",
                    "details": "The plain-text reading order is short, so important information may be missing or too sparse.",
                    "recommendation": "Expand role bullets and key sections with text-based content instead of relying on short labels.",
                }
            )

    missing_standard = [section for section in ("summary", "skills", "experience", "education") if not resume.standard_sections_present.get(section)]
    if missing_standard:
        score -= min(16, len(missing_standard) * config["missing_heading_penalty"])
        issues.append(
            {
                "severity": "high",
                "issue": "Missing standard sections",
                "details": f"The resume is missing standard ATS sections: {', '.join(missing_standard)}.",
                "recommendation": "Restore standard headings so ATS systems can map information to the right fields.",
            }
        )

    parsing_confidence = max(0.45, min(0.98, score / 100 - (0.015 * len(issues))))
    return _clamp_score(round(score)), parsing_confidence, issues


def _score_completeness(job: JobDescriptionAnalysis, resume: ResumeAnalysis, assessments: list[TermAssessment]) -> int:
    config = ATS_SCORING_CONFIG["completeness"]
    contact_score = sum(1 for value in resume.contact_signals.values() if value) / len(resume.contact_signals)
    summary_score = 1.0 if len(resume.section_text["summary"]) >= 90 else 0.72 if resume.section_text["summary"] else 0.0
    if any(item.term in job.required_skills and item.match_type for item in assessments):
        summary_score = min(1.0, summary_score + 0.08)
    achievement_score = min(1.0, resume.measurable_achievement_count / 4) if resume.measurable_achievement_count else 0.38

    relevant_sections = ["summary", "skills", "experience", "education"]
    if _job_mentions_optional_section(job, "projects"):
        relevant_sections.append("projects")
    if job.certifications:
        relevant_sections.append("certifications")
    section_score = sum(1 for section in relevant_sections if resume.standard_sections_present.get(section)) / len(relevant_sections)

    score = 100 * (
        config["contact_weight"] * contact_score
        + config["summary_weight"] * summary_score
        + config["achievement_weight"] * achievement_score
        + config["section_weight"] * section_score
    )
    return _clamp_score(round(score))


def _apply_parsing_cap(score: int, parsing_confidence: float) -> tuple[int, bool, str | None]:
    caps = ATS_SCORING_CONFIG["parsing_caps"]
    if parsing_confidence < caps["hard_cap_confidence"] and score > caps["hard_cap_score"]:
        return caps["hard_cap_score"], True, "Low parsing confidence capped the final ATS score."
    if parsing_confidence < caps["soft_cap_confidence"] and score > caps["soft_cap_score"]:
        return caps["soft_cap_score"], True, "Formatting risk lowered the final ATS ceiling."
    return score, False, None


def _build_keyword_outputs(assessments: list[TermAssessment], job: JobDescriptionAnalysis) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    matched_keywords: list[dict[str, object]] = []
    missing_keywords: list[dict[str, str]] = []
    high_priority_terms = set(job.required_skills + job.certifications)
    medium_priority_terms = set(job.preferred_skills + [term for term in job.tools if term not in high_priority_terms])

    for item in assessments:
        if item.match_type:
            matched_keywords.append(
                {
                    "keyword": item.term,
                    "importance": item.importance,
                    "match_type": item.match_type,
                    "source_sections": item.sections,
                    "evidence": item.evidence,
                }
            )
        else:
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
                    "details": _missing_keyword_reason(item.term, importance),
                }
            )

    matched_keywords.sort(key=lambda entry: (_importance_order(entry["importance"]), entry["keyword"]))
    missing_keywords.sort(key=lambda entry: (_importance_order(entry["importance"]), entry["keyword"]))
    return matched_keywords[:18], missing_keywords[:18]


def _missing_keyword_reason(term: str, importance: str) -> str:
    if importance == "high":
        return f"{term} appears to be a required qualification and is not clearly supported in the resume."
    if importance == "medium":
        return f"{term} is part of the preferred or tool stack language in the job posting."
    return f"{term} appears in the job description and could improve contextual keyword coverage."


def _build_critical_gaps(job: JobDescriptionAnalysis, resume: ResumeAnalysis, assessments: list[TermAssessment]) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    assessment_map = {item.term: item for item in assessments}
    for term in job.required_skills:
        item = assessment_map.get(term)
        if item and not item.match_type and item.category == "hard_skill":
            gaps.append(
                {
                    "title": f"Missing required skill: {term}",
                    "details": f"The role explicitly calls for {term}, but the resume does not show reliable ATS evidence for it.",
                    "impact": "This can materially reduce recruiter confidence and ATS ranking.",
                }
            )
    if job.years_required and resume.experience_years + 0.5 < job.years_required:
        gaps.append(
            {
                "title": "Experience level below stated requirement",
                "details": f"The role asks for about {job.years_required}+ years, while the resume shows roughly {resume.experience_years} years.",
                "impact": "This can reduce shortlist likelihood even if skills are relevant.",
            }
        )
    if job.certifications and not resume.section_text["certifications"].strip():
        gaps.append(
            {
                "title": "Required certification not found",
                "details": "The job posting mentions a certification or license requirement that is not present in the resume.",
                "impact": "Recruiters may treat this as a hard screen-out criterion.",
            }
        )
    if job.authorization_requirements and not any(best_match_type(term, resume.parse_preview) for term in job.authorization_requirements):
        gaps.append(
            {
                "title": "Work authorization not stated",
                "details": "The job posting references work authorization or sponsorship, but the resume does not address it.",
                "impact": "For strict hiring filters, this can reduce the match score immediately.",
            }
        )
    return gaps[:6]


def _build_suggestions(
    job: JobDescriptionAnalysis,
    section_scores: dict[str, int],
    missing_keywords: list[dict[str, str]],
    formatting_issues: list[dict[str, str]],
    critical_gaps: list[dict[str, str]],
) -> list[dict[str, str]]:
    suggestions: list[dict[str, str]] = []
    for gap in critical_gaps[:3]:
        suggestions.append(
            {
                "priority": "high",
                "title": gap["title"],
                "details": gap["details"],
                "issue_type": "content",
                "suggested_edit": "Address this directly in a truthful summary line, experience bullet, or certification entry.",
            }
        )
    for item in missing_keywords[:4]:
        suggestions.append(suggestion_for_missing_keyword(item["keyword"], priority=item["importance"]))
    for issue in formatting_issues[:2]:
        suggestions.append(suggestion_for_formatting(issue["issue"], issue["recommendation"], priority=issue["severity"]))
    weakest_sections = sorted(section_scores.items(), key=lambda item: item[1])[:2]
    for section_name, score in weakest_sections:
        if score >= 78:
            continue
        suggestions.append(
            {
                "priority": "medium",
                "title": f"Strengthen {section_name.replace('_', ' ')}",
                "details": f"This section is scoring {score}/100 and is one of the main reasons the ATS score is lower.",
                "issue_type": "content" if "formatting" not in section_name else "formatting",
                "suggested_edit": _section_edit_suggestion(section_name, job),
            }
        )
    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for suggestion in suggestions:
        key = suggestion["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(suggestion)
    return unique[:8]


def _section_edit_suggestion(section_name: str, job: JobDescriptionAnalysis) -> str:
    if section_name == "skills_match":
        focus_terms = ", ".join(job.required_skills[:3]) or "the role's must-have tools"
        return f"Mirror the target role's must-have language with truthful evidence for {focus_terms} in experience bullets, not only the skills list."
    if section_name == "experience_relevance":
        return "Rewrite 2-3 experience bullets to show role-relevant scope, domain context, and measurable outcomes."
    if section_name == "keyword_coverage":
        return "Use job language naturally in summary, experience, and projects instead of repeating a raw tool list."
    if section_name == "education_certifications":
        return "Clarify degree alignment or add missing certifications, location, or authorization details if they apply."
    if section_name == "formatting_parseability":
        return "Use consistent headings, dates, and a plain top-to-bottom structure so ATS systems can parse the document cleanly."
    return "Fill the missing section with direct evidence, measurable outcomes, and standard ATS-friendly headings."


def _build_comparison_view(job: JobDescriptionAnalysis, assessments: list[TermAssessment]) -> list[dict[str, object]]:
    assessment_map = {item.term: item for item in assessments}
    comparisons: list[dict[str, object]] = []
    for term in dedupe_preserve_order(job.required_skills + job.preferred_skills + job.tools)[:10]:
        assessment = assessment_map.get(term)
        if not assessment:
            continue
        if not assessment.match_type:
            status = "missing"
        elif assessment.match_type == "semantic" or assessment.sections == ["skills"]:
            status = "partial"
        else:
            status = "matched"
        comparisons.append(
            {
                "requirement": term,
                "importance": assessment.importance,
                "status": status,
                "evidence": assessment.evidence,
            }
        )
    return comparisons


def _build_explanation_points(
    section_scores: dict[str, int],
    matched_keywords: list[dict[str, object]],
    missing_keywords: list[dict[str, str]],
    formatting_issues: list[dict[str, str]],
    critical_gaps: list[dict[str, str]],
) -> tuple[list[str], list[str]]:
    strengths: list[str] = []
    risks: list[str] = []

    top_sections = sorted(section_scores.items(), key=lambda item: item[1], reverse=True)[:2]
    for key, score in top_sections:
        if score >= 80:
            strengths.append(f"{key.replace('_', ' ').title()} is a relative strength at {score}/100.")
    if matched_keywords:
        strongest_match = matched_keywords[0]
        strengths.append(
            f"{strongest_match['keyword']} is already supported with {strongest_match['match_type']} evidence in {', '.join(strongest_match['source_sections'])}."
        )

    low_sections = sorted(section_scores.items(), key=lambda item: item[1])[:2]
    for key, score in low_sections:
        if score < 78:
            risks.append(f"{key.replace('_', ' ').title()} is underperforming at {score}/100.")
    if missing_keywords:
        risks.append(f"Missing keywords include {', '.join(item['keyword'] for item in missing_keywords[:3])}.")
    if formatting_issues:
        risks.append(formatting_issues[0]["details"])
    if critical_gaps:
        risks.append(critical_gaps[0]["details"])
    return strengths[:4], risks[:4]


def _job_mentions_optional_section(job: JobDescriptionAnalysis, section_name: str) -> bool:
    keywords = ATS_SCORING_CONFIG["role_keywords_for_optional_sections"][section_name]
    haystack = normalize_text(" ".join([job.title, *job.responsibility_phrases, *job.action_phrases]))
    return any(keyword in haystack for keyword in keywords)


def _count_occurrences(term: str, text: str) -> int:
    count = 0
    normalized_text = normalize_text(text)
    for alias in aliases_for(term):
        escaped = re.escape(normalize_text(alias))
        count = max(count, len(re.findall(rf"(?<!\w){escaped}(?!\w)", normalized_text)))
    if not count and any(exact_phrase_present(alias, text) for alias in aliases_for(term)):
        return 1
    return count


def _importance_order(importance: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}[importance]


def _clamp_score(score: int) -> int:
    return max(0, min(100, score))
