from __future__ import annotations

from .ats_config import ATS_SCORING_CONFIG, legacy_score_label, score_label
from .ats_evidence import TermAssessment, build_term_assessments
from .ats_gap_analysis import build_gap_analysis
from .ats_normalization import (
    best_match_type,
    dedupe_preserve_order,
    is_strong_match_type,
    match_strength,
    normalize_text,
    similarity_ratio,
)
from .ats_readability import score_readability
from .ats_recommendations import build_explanation_panel
from .ats_role_matching import match_role, responsibility_alignment, years_alignment
from .ats_suggestions import build_suggestions, flatten_suggestions
from .job_description import JobDescriptionAnalysis
from .resume_parser import ResumeAnalysis


def score_resume(job: JobDescriptionAnalysis, resume: ResumeAnalysis) -> dict[str, object]:
    config = ATS_SCORING_CONFIG
    assessments = build_term_assessments(job, resume)
    role_match = match_role(job, resume)
    readability = score_readability(resume, assessments)

    job_breakdown = {
        "skills_match": _score_skills(job, assessments),
        "experience_relevance": _score_experience(job, resume, assessments, role_match.score),
        "keyword_coverage": _score_keyword_coverage(assessments),
        "projects_relevance": _score_projects(job, resume, assessments),
        "education_certification_match": _score_education(job, resume, assessments),
        "seniority_years_match": years_alignment(job.years_required, resume.experience_years),
        "role_alignment": role_match.score,
    }
    job_match_raw = round(sum(config["job_match_weights"][key] * value for key, value in job_breakdown.items()))

    gap_analysis = build_gap_analysis(job, resume, assessments, role_match)
    job_match_score, cap_applied, cap_reason = _calibrate_job_match(job_match_raw, job, resume, assessments, gap_analysis, role_match.score)
    overall_raw = round(
        config["overall_weights"]["job_match"] * job_match_score
        + config["overall_weights"]["readability"] * readability.score
    )
    overall_score, parsing_cap_applied, parsing_cap_reason = _apply_parsing_cap(overall_raw, readability.parsing_confidence)
    score_cap_applied = cap_applied or parsing_cap_applied
    score_cap_reason = cap_reason or parsing_cap_reason

    matched_keywords = _build_matched_keywords(assessments)
    strong_evidence_skills = _evidence_skills(assessments, minimum_tier=3)
    weak_evidence_skills = _weak_evidence_skills(assessments)
    suggestions_grouped = build_suggestions(
        job,
        job_breakdown,
        readability.sub_scores,
        gap_analysis,
        assessments,
        readability.formatting_issues,
        readability.stuffing_warnings,
        role_match,
    )
    comparison_view = _build_comparison_view(job, assessments)
    confidence_score = _confidence_score(job, resume, assessments, readability.parsing_confidence, job_match_score)
    strengths, risks = _build_explanation_points(
        job_breakdown,
        readability.sub_scores,
        matched_keywords,
        gap_analysis["missing_keywords"],
        readability.formatting_issues,
        gap_analysis["critical_gaps"],
        readability.stuffing_warnings,
    )
    explanation_panel = build_explanation_panel(
        overall_score=overall_score,
        parsing_confidence=readability.parsing_confidence,
        strengths=strengths,
        risks=risks,
    )

    section_scores = {
        "skills_match": job_breakdown["skills_match"],
        "experience_relevance": job_breakdown["experience_relevance"],
        "keyword_coverage": job_breakdown["keyword_coverage"],
        "education_certifications": job_breakdown["education_certification_match"],
        "formatting_parseability": readability.sub_scores["parseability"],
        "completeness": readability.sub_scores["section_completeness"],
    }

    return {
        "overall_score": overall_score,
        "overall_ats_score": overall_score,
        "job_match_score": job_match_score,
        "ats_readability_score": readability.score,
        "confidence_score": confidence_score,
        "confidence_label": legacy_score_label(overall_score),
        "match_quality_label": score_label(overall_score),
        "parsing_confidence": readability.parsing_confidence,
        "score_cap_applied": score_cap_applied,
        "score_cap_reason": score_cap_reason,
        "summary": explanation_panel["summary"],
        "section_scores": section_scores,
        "score_breakdown": {
            "job_match": job_breakdown,
            "ats_readability": readability.sub_scores,
            "weights": config["overall_weights"],
        },
        "matched_keywords": matched_keywords,
        "matched_skills": matched_keywords,
        "strong_evidence_skills": strong_evidence_skills,
        "weak_evidence_skills": weak_evidence_skills,
        "missing_keywords": gap_analysis["missing_keywords"],
        "missing_required_skills": gap_analysis["missing_required_skills"],
        "missing_preferred_skills": gap_analysis["missing_preferred_skills"],
        "missing_role_signals": gap_analysis["missing_role_signals"],
        "missing_education_certifications": gap_analysis["missing_education_certifications"],
        "formatting_issues": readability.formatting_issues,
        "critical_gaps": gap_analysis["critical_gaps"],
        "stuffing_warnings": readability.stuffing_warnings,
        "suggestions": suggestions_grouped,
        "improvement_suggestions": flatten_suggestions(suggestions_grouped),
        "parse_preview": resume.parse_preview,
        "comparison_view": comparison_view,
        "explanation_panel": explanation_panel,
    }


def _score_skills(job: JobDescriptionAnalysis, assessments: list[TermAssessment]) -> int:
    config = ATS_SCORING_CONFIG["skills"]
    required_terms = set(job.required_skills)
    preferred_terms = set(job.preferred_skills) or {term for term in job.tools if term not in required_terms}
    required_score = _weighted_term_average([item for item in assessments if item.term in required_terms], config)
    preferred_score = _weighted_term_average([item for item in assessments if item.term in preferred_terms], config)
    total = config["required_weight"] * required_score + config["preferred_weight"] * preferred_score

    missing_required_hard_skills = sum(
        1
        for item in assessments
        if item.term in required_terms and item.category == "hard_skill" and not is_strong_match_type(item.match_type)
    )
    total -= min(20, missing_required_hard_skills * config["critical_required_skill_penalty"])
    return _clamp_score(round(total))


def _weighted_term_average(assessments: list[TermAssessment], config: dict[str, object]) -> float:
    if not assessments:
        return 78.0
    weighted_total = 0.0
    total_weight = 0.0
    for item in assessments:
        category_weight = config["hard_skill_weight"] if item.category == "hard_skill" else config["soft_skill_weight"]
        weighted_total += _term_score(item, config) * category_weight
        total_weight += category_weight
    return (weighted_total / total_weight) if total_weight else 0.0


def _term_score(item: TermAssessment, config: dict[str, object]) -> float:
    if not item.match_type:
        return 0.0
    base = match_strength(item.match_type)
    if item.match_type == "related":
        base = min(base, config["related_match_score"])
    best_section_bonus = max((config["section_bonus"].get(section, 0.6) for section in item.sections), default=0.0)
    tier_multiplier = config["evidence_tier_multiplier"].get(item.evidence_tier, 0.0)
    quality_multiplier = 0.82 + (min(100, item.evidence_quality) / 100) * 0.28
    score = 100 * base * best_section_bonus * tier_multiplier * quality_multiplier
    return min(100.0, score)


def _score_experience(
    job: JobDescriptionAnalysis,
    resume: ResumeAnalysis,
    assessments: list[TermAssessment],
    role_alignment_score: int,
) -> int:
    config = ATS_SCORING_CONFIG["experience"]
    responsibility_score = responsibility_alignment(job, resume)
    domain_score = _domain_alignment(job, assessments)
    years_score = years_alignment(job.years_required, resume.experience_years)
    evidence_score = _experience_evidence_alignment(job, assessments)
    score = (
        config["title_alignment_weight"] * role_alignment_score
        + config["responsibility_weight"] * responsibility_score
        + config["domain_weight"] * domain_score
        + config["years_weight"] * years_score
        + config["evidence_weight"] * evidence_score
    )
    return _clamp_score(round(score))


def _domain_alignment(job: JobDescriptionAnalysis, assessments: list[TermAssessment]) -> int:
    domain_terms = [item for item in assessments if item.term in job.industry_keywords]
    if not domain_terms:
        return 78
    matched = sum(1 for item in domain_terms if item.is_matched)
    return round(100 * matched / len(domain_terms))


def _experience_evidence_alignment(job: JobDescriptionAnalysis, assessments: list[TermAssessment]) -> int:
    relevant = [item for item in assessments if item.term in set(job.required_skills + job.tools)]
    if not relevant:
        return 76
    matched = 0.0
    for item in relevant:
        if item.evidence_tier >= 4:
            matched += 1.0
        elif item.evidence_tier >= 3:
            matched += 0.85
        elif item.evidence_tier == 2:
            matched += 0.62
        elif item.evidence_tier == 1:
            matched += 0.36
    return round(100 * min(1.0, matched / len(relevant)))


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
        section_bonus = max((config["section_weights"].get(section, 0.5) for section in item.sections), default=0.0)
        tier_bonus = {1: 0.58, 2: 0.76, 3: 0.9, 4: 1.0}.get(item.evidence_tier, 0.0)
        weighted_total += importance_weight * min(1.0, match_strength(item.match_type) * section_bonus * tier_bonus)

        if item.occurrence_count > config["stuffing_repeat_threshold"]:
            penalty += (item.occurrence_count - config["stuffing_repeat_threshold"]) * config["stuffing_penalty_per_extra"]
        if item.is_skills_only and item.importance in {"high", "medium"}:
            penalty += config["skills_only_penalty"]
        if item.match_type == "related":
            penalty += config["shallow_keyword_penalty"]

    score = 100 * (weighted_total / total_weight) if total_weight else 0.0
    return _clamp_score(round(score - penalty))


def _score_projects(job: JobDescriptionAnalysis, resume: ResumeAnalysis, assessments: list[TermAssessment]) -> int:
    config = ATS_SCORING_CONFIG["projects"]
    project_text = resume.section_text.get("projects", "")
    relevant_terms = [item for item in assessments if item.term in set(job.required_skills + job.preferred_skills + job.tools)]
    if not project_text:
        if _job_mentions_projects(job):
            return 42
        return config["baseline_without_project_requirement"]
    if not relevant_terms:
        return 72
    project_matches = [item for item in relevant_terms if "projects" in item.sections]
    overlap_score = round(100 * len(project_matches) / len(relevant_terms))
    quality_score = round(
        sum(item.evidence_quality for item in project_matches) / len(project_matches)
    ) if project_matches else 35
    presence_score = 100 if project_text else 0
    score = (
        config["skill_overlap_weight"] * overlap_score
        + config["evidence_quality_weight"] * quality_score
        + config["project_presence_weight"] * presence_score
    )
    return _clamp_score(round(score))


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
        degree_score = 1.0 if any(match in {"exact", "alias", "phrase"} for match in degree_matches) else 0.65 if any(degree_matches) else 0.0

    cert_score = 0.82 if certifications_text else 0.7
    if job.certifications:
        cert_matches = [item for item in assessments if item.term in job.certifications and item.is_matched]
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


def _calibrate_job_match(
    score: int,
    job: JobDescriptionAnalysis,
    resume: ResumeAnalysis,
    assessments: list[TermAssessment],
    gap_analysis: dict[str, object],
    role_alignment_score: int,
) -> tuple[int, bool, str | None]:
    caps = ATS_SCORING_CONFIG["calibration_caps"]
    cap = 100
    reasons: list[str] = []
    missing_required_hard = [
        item for item in gap_analysis["missing_required_skills"] if item.get("category") == "hard_skill"
    ]
    if len(missing_required_hard) >= 2:
        cap = min(cap, caps["multiple_required_hard_skills_missing"])
        reasons.append("Multiple required hard skills are missing.")
    elif len(missing_required_hard) == 1:
        cap = min(cap, caps["one_required_hard_skill_missing"])
        reasons.append("A required hard skill is missing.")
    if role_alignment_score < 45:
        cap = min(cap, caps["core_role_missing"])
        reasons.append("Core role alignment is weak.")
    if job.years_required and resume.experience_years + 0.5 < job.years_required:
        cap = min(cap, caps["years_mismatch"])
        reasons.append("Years of experience appear below the stated requirement.")
    if _mostly_shallow_evidence(assessments):
        cap = min(cap, caps["mostly_shallow_evidence"])
        reasons.append("Most matched skills are supported only by shallow/list evidence.")
    calibrated = min(score, cap)
    if calibrated < score:
        return calibrated, True, " ".join(reasons)
    return score, False, None


def _apply_parsing_cap(score: int, parsing_confidence: float) -> tuple[int, bool, str | None]:
    caps = ATS_SCORING_CONFIG["parsing_caps"]
    if parsing_confidence < caps["hard_cap_confidence"] and score > caps["hard_cap_score"]:
        return caps["hard_cap_score"], True, "Low parsing confidence capped the final ATS score."
    if parsing_confidence < caps["soft_cap_confidence"] and score > caps["soft_cap_score"]:
        return caps["soft_cap_score"], True, "Formatting risk lowered the final ATS ceiling."
    return score, False, None


def _build_matched_keywords(assessments: list[TermAssessment]) -> list[dict[str, object]]:
    matched: list[dict[str, object]] = []
    for item in assessments:
        if not item.is_matched:
            continue
        matched.append(
            {
                "keyword": item.term,
                "importance": item.importance,
                "match_type": item.match_type,
                "source_sections": item.sections,
                "evidence": item.evidence,
                "evidence_tier": item.evidence_tier,
                "evidence_quality": item.evidence_quality,
            }
        )
    matched.sort(key=lambda entry: (_importance_order(entry["importance"]), -entry["evidence_tier"], entry["keyword"]))
    return matched[:22]


def _evidence_skills(assessments: list[TermAssessment], *, minimum_tier: int) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for item in assessments:
        if item.category != "hard_skill" or item.evidence_tier < minimum_tier:
            continue
        output.append(
            {
                "keyword": item.term,
                "evidence_tier": item.evidence_tier,
                "evidence_quality": item.evidence_quality,
                "source_sections": item.sections,
                "evidence": item.evidence[:2],
            }
        )
    output.sort(key=lambda entry: (-entry["evidence_tier"], -entry["evidence_quality"], entry["keyword"]))
    return output[:12]


def _weak_evidence_skills(assessments: list[TermAssessment]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for item in assessments:
        if item.category != "hard_skill" or not item.is_matched or item.evidence_tier > 1:
            continue
        output.append(
            {
                "keyword": item.term,
                "evidence_tier": item.evidence_tier,
                "evidence_quality": item.evidence_quality,
                "source_sections": item.sections,
                "evidence": item.evidence[:2],
            }
        )
    output.sort(key=lambda entry: (_importance_order(next((item.importance for item in assessments if item.term == entry["keyword"]), "low")), entry["keyword"]))
    return output[:12]


def _build_comparison_view(job: JobDescriptionAnalysis, assessments: list[TermAssessment]) -> list[dict[str, object]]:
    assessment_map = {item.term: item for item in assessments}
    comparisons: list[dict[str, object]] = []
    for term in dedupe_preserve_order(job.required_skills + job.preferred_skills + job.tools)[:12]:
        assessment = assessment_map.get(term)
        if not assessment:
            continue
        if not assessment.is_matched:
            status = "missing"
        elif assessment.match_type == "related" or assessment.evidence_tier <= 1:
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


def _confidence_score(
    job: JobDescriptionAnalysis,
    resume: ResumeAnalysis,
    assessments: list[TermAssessment],
    parsing_confidence: float,
    job_match_score: int,
) -> float:
    jd_signal_count = len(job.required_skills) + len(job.preferred_skills) + len(job.tools) + len(job.responsibility_phrases)
    resume_signal_count = sum(1 for section in ("summary", "skills", "experience", "education") if resume.section_text.get(section))
    matched = [item for item in assessments if item.is_matched]
    shallow_ratio = (
        sum(1 for item in matched if item.evidence_tier <= 1) / len(matched)
        if matched
        else 1.0
    )
    confidence = 0.40 + parsing_confidence * 0.32
    confidence += min(0.12, jd_signal_count * 0.01)
    confidence += min(0.08, resume_signal_count * 0.02)
    confidence += min(0.08, len([item for item in matched if item.evidence_tier >= 3]) * 0.012)
    confidence -= shallow_ratio * 0.12
    if job_match_score < 35 and jd_signal_count < 4:
        confidence -= 0.08
    return round(max(0.35, min(0.98, confidence)), 2)


def _build_explanation_points(
    job_breakdown: dict[str, int],
    readability_breakdown: dict[str, int],
    matched_keywords: list[dict[str, object]],
    missing_keywords: list[dict[str, str]],
    formatting_issues: list[dict[str, str]],
    critical_gaps: list[dict[str, str]],
    stuffing_warnings: list[dict[str, str]],
) -> tuple[list[str], list[str]]:
    strengths: list[str] = []
    risks: list[str] = []

    top_job = sorted(job_breakdown.items(), key=lambda item: item[1], reverse=True)[:2]
    for key, score in top_job:
        if score >= 80:
            strengths.append(f"{key.replace('_', ' ').title()} is a relative strength at {score}/100.")
    top_readability = sorted(readability_breakdown.items(), key=lambda item: item[1], reverse=True)[:1]
    for key, score in top_readability:
        if score >= 88:
            strengths.append(f"{key.replace('_', ' ').title()} supports ATS readability at {score}/100.")
    strong_match = next((item for item in matched_keywords if item.get("evidence_tier", 0) >= 3), matched_keywords[0] if matched_keywords else None)
    if strong_match:
        strengths.append(
            f"{strong_match['keyword']} is supported with {strong_match['match_type']} evidence in {', '.join(strong_match['source_sections'])}."
        )

    low_job = sorted(job_breakdown.items(), key=lambda item: item[1])[:2]
    for key, score in low_job:
        if score < 74:
            risks.append(f"{key.replace('_', ' ').title()} is underperforming at {score}/100.")
    if missing_keywords:
        risks.append(f"Missing keywords include {', '.join(item['keyword'] for item in missing_keywords[:3])}.")
    if critical_gaps:
        risks.append(critical_gaps[0]["details"])
    if stuffing_warnings:
        risks.append(stuffing_warnings[0]["details"])
    elif formatting_issues:
        risks.append(formatting_issues[0]["details"])
    return strengths[:4], risks[:4]


def _mostly_shallow_evidence(assessments: list[TermAssessment]) -> bool:
    important_matches = [item for item in assessments if item.importance in {"high", "medium"} and item.is_matched]
    if len(important_matches) < 3:
        return False
    shallow = sum(1 for item in important_matches if item.evidence_tier <= 1)
    return shallow / len(important_matches) >= 0.58


def _job_mentions_projects(job: JobDescriptionAnalysis) -> bool:
    haystack = normalize_text(" ".join([job.title, *job.responsibility_phrases, *job.action_phrases]))
    return any(keyword in haystack for keyword in ATS_SCORING_CONFIG["role_keywords_for_optional_sections"]["projects"])


def _importance_order(importance: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}[importance]


def _clamp_score(score: int) -> int:
    return max(0, min(100, score))
