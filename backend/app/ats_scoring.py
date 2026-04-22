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
from .ats_semantic_matching import SemanticMatchResult, match_semantic_requirements
from .ats_suggestions import build_suggestions, flatten_suggestions
from .job_description import JobDescriptionAnalysis
from .resume_parser import ResumeAnalysis


def score_resume(job: JobDescriptionAnalysis, resume: ResumeAnalysis) -> dict[str, object]:
    config = ATS_SCORING_CONFIG
    assessments = build_term_assessments(job, resume)
    role_match = match_role(job, resume)
    semantic_match = match_semantic_requirements(job, resume)
    readability = score_readability(resume, assessments)
    weight_profile_name, job_match_weights = _select_role_weight_profile(job, role_match.job_family)

    job_breakdown = {
        "skills_match": _score_skills(job, assessments),
        "semantic_requirement_match": semantic_match.semantic_requirement_match_score,
        "responsibility_match": semantic_match.responsibility_match_score,
        "experience_relevance": _score_experience(job, resume, assessments, role_match.score, semantic_match.responsibility_match_score),
        "keyword_coverage": _score_keyword_coverage(assessments),
        "projects_relevance": _score_projects(job, resume, assessments),
        "education_certification_match": _score_education(job, resume, assessments),
        "seniority_years_match": years_alignment(job.years_required, resume.experience_years),
        "role_alignment": role_match.score,
    }
    job_match_raw = round(sum(job_match_weights[key] * value for key, value in job_breakdown.items()))

    gap_analysis = build_gap_analysis(job, resume, assessments, role_match)
    semantic_critical_gaps = _semantic_critical_gaps(semantic_match)
    if semantic_critical_gaps:
        gap_analysis["critical_gaps"] = [*gap_analysis["critical_gaps"], *semantic_critical_gaps][:8]
    job_match_score, job_caps = _calibrate_job_match(job_match_raw, job, resume, assessments, gap_analysis, role_match, semantic_match, job_breakdown)
    overall_raw = round(
        config["overall_weights"]["job_match"] * job_match_score
        + config["overall_weights"]["readability"] * readability.score
    )
    overall_score, parsing_caps = _apply_parsing_cap(overall_raw, readability.parsing_confidence)
    score_caps_applied = [*job_caps, *parsing_caps]
    score_cap_applied = bool(score_caps_applied)
    score_cap_reason = " ".join(str(item["reason"]) for item in score_caps_applied) or None

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
    confidence_score, confidence_factors = _confidence_score(job, resume, assessments, readability.parsing_confidence, job_match_score, semantic_match)
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
        "confidence_factors": confidence_factors,
        "confidence_label": legacy_score_label(overall_score),
        "match_quality_label": score_label(overall_score),
        "parsing_confidence": readability.parsing_confidence,
        "score_cap_applied": score_cap_applied,
        "score_cap_reason": score_cap_reason,
        "score_caps_applied": score_caps_applied,
        "detected_role_family": role_match.job_family or "",
        "detected_resume_role_family": role_match.resume_family or "",
        "weight_profile_name": weight_profile_name,
        "weight_profile_used": job_match_weights,
        "matched_requirements": semantic_match.matched_requirements,
        "weakly_matched_requirements": semantic_match.weakly_matched_requirements,
        "unmatched_requirements": semantic_match.unmatched_requirements,
        "matched_responsibilities": semantic_match.matched_responsibilities,
        "missing_responsibilities": semantic_match.missing_responsibilities,
        "semantic_requirement_matches": [_semantic_match_payload(match) for match in semantic_match.requirement_matches[:14]],
        "responsibility_match_score": semantic_match.responsibility_match_score,
        "summary": explanation_panel["summary"],
        "section_scores": section_scores,
        "score_breakdown": {
            "job_match": job_breakdown,
            "ats_readability": readability.sub_scores,
            "weights": config["overall_weights"],
            "job_match_weights": job_match_weights,
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
    semantic_responsibility_score: int | None = None,
) -> int:
    config = ATS_SCORING_CONFIG["experience"]
    responsibility_score = semantic_responsibility_score if semantic_responsibility_score is not None else responsibility_alignment(job, resume)
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
    role_match,
    semantic_match: SemanticMatchResult,
    job_breakdown: dict[str, int],
) -> tuple[int, list[dict[str, object]]]:
    caps = ATS_SCORING_CONFIG["calibration_caps"]
    cap = 100
    applied: list[dict[str, object]] = []

    def add_cap(name: str, cap_value: int, reason: str, trigger: str) -> None:
        nonlocal cap
        cap = min(cap, cap_value)
        applied.append(
            {
                "cap_name": name,
                "cap": cap_value,
                "reason": reason,
                "triggered_by": trigger,
            }
        )

    missing_required_hard = [
        item for item in gap_analysis["missing_required_skills"] if item.get("category") == "hard_skill"
    ]
    if len(missing_required_hard) >= 2:
        add_cap(
            "multiple_required_hard_skills_missing",
            caps["multiple_required_hard_skills_missing"],
            "Multiple required hard skills are missing.",
            ", ".join(item["keyword"] for item in missing_required_hard[:4]),
        )
    elif len(missing_required_hard) == 1:
        add_cap(
            "one_required_hard_skill_missing",
            caps["one_required_hard_skill_missing"],
            "A required hard skill is missing.",
            missing_required_hard[0]["keyword"],
        )
    if role_match.score < 45:
        add_cap("core_role_missing", caps["core_role_missing"], "Core role alignment is weak.", f"role_alignment={role_match.score}")
    if role_match.job_family and role_match.resume_family and role_match.family_similarity < 0.45:
        add_cap(
            "role_family_mismatch",
            caps["role_family_mismatch"],
            "Detected resume role family is far from the JD role family.",
            f"{role_match.resume_family} vs {role_match.job_family}",
        )
    if job.years_required and resume.experience_years + 0.5 < job.years_required:
        add_cap(
            "years_mismatch",
            caps["years_mismatch"],
            "Years of experience appear below the stated requirement.",
            f"resume_years={resume.experience_years}, required_years={job.years_required}",
        )
    if semantic_match.requirement_matches and semantic_match.semantic_requirement_match_score < 46 and semantic_match.responsibility_match_score < 50:
        add_cap(
            "weak_semantic_or_responsibility",
            caps["weak_semantic_or_responsibility"],
            "Requirement and responsibility bullet evidence is weak.",
            f"semantic={semantic_match.semantic_requirement_match_score}, responsibility={semantic_match.responsibility_match_score}",
        )
    if len(semantic_match.requirement_matches) >= 3 and semantic_match.strong_bullet_match_count == 0:
        add_cap(
            "no_strong_bullet_evidence",
            caps["no_strong_bullet_evidence"],
            "No JD requirement has strong experience or project bullet evidence.",
            "strong_bullet_match_count=0",
        )
    if job_breakdown["skills_match"] >= 78 and max(job_breakdown["semantic_requirement_match"], job_breakdown["responsibility_match"]) < 55:
        add_cap(
            "skills_only_without_context",
            caps["skills_only_without_context"],
            "Keyword presence is not supported by enough contextual work evidence.",
            f"skills={job_breakdown['skills_match']}, semantic={job_breakdown['semantic_requirement_match']}, responsibility={job_breakdown['responsibility_match']}",
        )
    if _mostly_shallow_evidence(assessments):
        add_cap(
            "mostly_shallow_evidence",
            caps["mostly_shallow_evidence"],
            "Most matched skills are supported only by shallow/list evidence.",
            "evidence_tier<=1 for most important matches",
        )
    calibrated = min(score, cap)
    if applied:
        return calibrated, applied
    return score, []


def _apply_parsing_cap(score: int, parsing_confidence: float) -> tuple[int, list[dict[str, object]]]:
    caps = ATS_SCORING_CONFIG["parsing_caps"]
    if parsing_confidence < caps["hard_cap_confidence"] and score > caps["hard_cap_score"]:
        return caps["hard_cap_score"], [
            {
                "cap_name": "low_parsing_confidence_hard_cap",
                "cap": caps["hard_cap_score"],
                "reason": "Low parsing confidence capped the final ATS score.",
                "triggered_by": f"parsing_confidence={round(parsing_confidence, 2)}",
            }
        ]
    if parsing_confidence < caps["soft_cap_confidence"] and score > caps["soft_cap_score"]:
        return caps["soft_cap_score"], [
            {
                "cap_name": "low_parsing_confidence_soft_cap",
                "cap": caps["soft_cap_score"],
                "reason": "Formatting risk lowered the final ATS ceiling.",
                "triggered_by": f"parsing_confidence={round(parsing_confidence, 2)}",
            }
        ]
    return score, []


def _select_role_weight_profile(job: JobDescriptionAnalysis, job_family: str | None) -> tuple[str, dict[str, float]]:
    profiles = ATS_SCORING_CONFIG["role_weight_profiles"]
    family = job_family or "default"
    seniority = _job_seniority(job)
    candidate_keys = []
    if seniority and family != "default":
        candidate_keys.append(f"{seniority}_{family}")
    candidate_keys.extend([family, "default"])
    for key in candidate_keys:
        if key in profiles:
            weights = _normalized_weights(profiles[key])
            return key, weights
    return "default", _normalized_weights(profiles["default"])


def _job_seniority(job: JobDescriptionAnalysis) -> str | None:
    haystack = normalize_text(" ".join([job.title, job.source.description, job.source.text[:1200]]))
    if any(token in haystack for token in ("intern", "internship", "trainee", "entry level", "junior", "jr", "associate")):
        return "entry"
    if any(token in haystack for token in ("senior", "sr", "lead", "principal", "staff")) or (job.years_required and job.years_required >= 5):
        return "senior"
    return None


def _normalized_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values()) or 1.0
    return {key: round(value / total, 4) for key, value in weights.items()}


def _semantic_critical_gaps(semantic_match: SemanticMatchResult) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    for item in semantic_match.unmatched_requirements[:2]:
        requirement = str(item.get("job_requirement", "Job requirement"))
        gaps.append(
            {
                "title": "Missing requirement evidence",
                "details": f"The JD requirement is not supported by a strong resume bullet: {requirement}",
                "impact": "Recruiters and ATS matching systems tend to reward concrete work evidence over isolated keywords.",
            }
        )
    for item in semantic_match.missing_responsibilities[:1]:
        responsibility = str(item.get("responsibility", "target responsibility"))
        gaps.append(
            {
                "title": "Missing responsibility evidence",
                "details": f"The resume does not show strong bullet-level evidence for: {responsibility}",
                "impact": "A resume can contain the right tools but still score lower when the expected work is not demonstrated.",
            }
        )
    return gaps[:3]


def _semantic_match_payload(match) -> dict[str, object]:
    return {
        "job_requirement": match.job_requirement,
        "matched_resume_bullet": match.matched_resume_bullet,
        "resume_section": match.resume_section,
        "semantic_score": match.semantic_score,
        "match_strength": match.match_strength,
        "matched_signals": match.matched_signals,
    }


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
    semantic_match: SemanticMatchResult,
) -> tuple[float, dict[str, float]]:
    jd_signal_count = len(job.required_skills) + len(job.preferred_skills) + len(job.tools) + len(job.responsibility_phrases)
    resume_signal_count = sum(1 for section in ("summary", "skills", "experience", "education") if resume.section_text.get(section))
    matched = [item for item in assessments if item.is_matched]
    shallow_ratio = (
        sum(1 for item in matched if item.evidence_tier <= 1) / len(matched)
        if matched
        else 1.0
    )
    requirement_count = len(semantic_match.requirement_matches)
    resume_bullet_count = sum(len(resume.section_lines.get(section, [])) for section in ("experience", "projects"))
    strong_evidence_count = len([item for item in matched if item.evidence_tier >= 3])
    required_signal_count = len(job.required_skills) + len(job.responsibility_phrases) + requirement_count

    jd_parse_quality = 0.25
    jd_parse_quality += min(0.32, requirement_count * 0.045)
    jd_parse_quality += min(0.26, jd_signal_count * 0.02)
    jd_parse_quality += 0.10 if job.title and job.title != "Target Role" else 0.0
    if requirement_count < 2 and jd_signal_count < 5:
        jd_parse_quality = min(jd_parse_quality, 0.55)

    standard_sections = sum(1 for present in resume.standard_sections_present.values() if present)
    resume_parse_quality = parsing_confidence * 0.58 + (standard_sections / 6) * 0.24 + min(0.18, resume_bullet_count * 0.018)

    relevant_terms = [item for item in assessments if item.importance in {"high", "medium"}]
    evidence_coverage = (
        sum(1.0 if item.evidence_tier >= 3 else 0.55 if item.evidence_tier == 2 else 0.2 if item.is_matched else 0.0 for item in relevant_terms)
        / len(relevant_terms)
        if relevant_terms
        else 0.45
    )
    semantic_coverage = 0.60 * semantic_match.semantic_coverage + 0.40 * (semantic_match.semantic_requirement_match_score / 100)
    signal_density = min(1.0, (required_signal_count + resume_bullet_count + strong_evidence_count) / 24)

    factors = {
        "jd_parse_quality": round(max(0.0, min(1.0, jd_parse_quality)), 2),
        "resume_parse_quality": round(max(0.0, min(1.0, resume_parse_quality)), 2),
        "evidence_coverage": round(max(0.0, min(1.0, evidence_coverage)), 2),
        "semantic_coverage": round(max(0.0, min(1.0, semantic_coverage)), 2),
        "signal_density": round(max(0.0, min(1.0, signal_density)), 2),
    }

    confidence = (
        0.24 * factors["jd_parse_quality"]
        + 0.22 * factors["resume_parse_quality"]
        + 0.22 * factors["evidence_coverage"]
        + 0.22 * factors["semantic_coverage"]
        + 0.10 * factors["signal_density"]
    )
    confidence -= shallow_ratio * 0.10
    if job_match_score < 35 and jd_signal_count < 4:
        confidence -= 0.08
    if requirement_count < 2 or resume_bullet_count < 2:
        confidence -= 0.06
    return round(max(0.25, min(0.98, confidence)), 2), factors


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
