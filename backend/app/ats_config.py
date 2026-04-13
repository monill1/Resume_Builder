from __future__ import annotations

ATS_SCORING_CONFIG = {
    "weights": {
        "skills_match": 0.30,
        "experience_relevance": 0.20,
        "keyword_coverage": 0.15,
        "education_certifications": 0.10,
        "formatting_parseability": 0.15,
        "completeness": 0.10,
    },
    "skills": {
        "required_weight": 0.72,
        "preferred_weight": 0.28,
        "hard_skill_weight": 0.72,
        "soft_skill_weight": 0.28,
        "exact_match_score": 1.0,
        "semantic_match_score": 0.72,
        "section_bonus": {
            "experience": 1.0,
            "projects": 0.94,
            "summary": 0.82,
            "skills": 0.62,
            "education": 0.7,
            "certifications": 0.75,
        },
        "context_bonus": {
            "measurable_bullet": 1.08,
            "action_or_achievement": 1.04,
            "list_only": 0.92,
        },
        "critical_required_skill_penalty": 8,
    },
    "keyword_coverage": {
        "section_weights": {
            "summary": 1.0,
            "skills": 0.55,
            "experience": 1.25,
            "projects": 1.15,
            "education": 0.7,
            "certifications": 0.75,
        },
        "exact_match_score": 1.0,
        "semantic_match_score": 0.7,
        "max_repetition_credit": 2,
        "stuffing_repeat_threshold": 3,
        "stuffing_penalty_per_extra": 3,
        "skills_only_penalty": 4,
    },
    "experience": {
        "title_alignment_weight": 0.30,
        "domain_weight": 0.23,
        "years_weight": 0.20,
        "evidence_weight": 0.27,
    },
    "education": {
        "baseline_without_explicit_requirement": 84,
        "degree_weight": 0.48,
        "certification_weight": 0.26,
        "location_weight": 0.14,
        "authorization_weight": 0.12,
    },
    "formatting": {
        "base_score": 96,
        "missing_heading_penalty": 8,
        "missing_contact_penalty": 12,
        "date_inconsistency_penalty": 7,
        "unclear_section_order_penalty": 6,
        "low_parse_preview_penalty": 6,
        "no_projects_when_relevant_penalty": 4,
        "no_certifications_when_required_penalty": 8,
    },
    "completeness": {
        "contact_weight": 0.28,
        "summary_weight": 0.20,
        "achievement_weight": 0.28,
        "section_weight": 0.24,
    },
    "parsing_caps": {
        "soft_cap_confidence": 0.74,
        "soft_cap_score": 82,
        "hard_cap_confidence": 0.58,
        "hard_cap_score": 68,
    },
    "standard_sections": [
        "summary",
        "skills",
        "experience",
        "education",
        "projects",
        "certifications",
    ],
    "role_keywords_for_optional_sections": {
        "projects": {"portfolio", "project", "build", "hands-on", "prototype", "github"},
        "certifications": {"certification", "certificate", "certified", "license", "licensed"},
    },
}


def score_label(score: int) -> str:
    if score >= 85:
        return "Strong Match"
    if score >= 70:
        return "Moderate Match"
    return "Weak Match"
