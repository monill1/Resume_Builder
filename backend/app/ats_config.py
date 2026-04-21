from __future__ import annotations

ATS_SCORING_CONFIG = {
    "overall_weights": {
        "job_match": 0.75,
        "readability": 0.25,
    },
    "legacy_weights": {
        "skills_match": 0.30,
        "experience_relevance": 0.20,
        "keyword_coverage": 0.15,
        "education_certifications": 0.10,
        "formatting_parseability": 0.15,
        "completeness": 0.10,
    },
    "job_match_weights": {
        "skills_match": 0.26,
        "experience_relevance": 0.20,
        "keyword_coverage": 0.16,
        "projects_relevance": 0.12,
        "education_certification_match": 0.08,
        "seniority_years_match": 0.08,
        "role_alignment": 0.10,
    },
    "readability_weights": {
        "section_completeness": 0.18,
        "section_heading_detection": 0.15,
        "parseability": 0.18,
        "bullet_clarity": 0.16,
        "contact_info_presence": 0.12,
        "date_consistency": 0.10,
        "tables_icons_symbols": 0.05,
        "repetition_stuffing": 0.06,
    },
    "skills": {
        "required_weight": 0.72,
        "preferred_weight": 0.28,
        "hard_skill_weight": 0.72,
        "soft_skill_weight": 0.28,
        "exact_match_score": 1.0,
        "alias_match_score": 0.94,
        "phrase_match_score": 0.84,
        "fuzzy_match_score": 0.76,
        "related_match_score": 0.52,
        "semantic_match_score": 0.72,
        "section_bonus": {
            "experience": 1.05,
            "projects": 0.98,
            "summary": 0.82,
            "skills": 0.58,
            "education": 0.7,
            "certifications": 0.75,
        },
        "context_bonus": {
            "measurable_bullet": 1.12,
            "action_or_achievement": 1.05,
            "list_only": 0.92,
        },
        "evidence_tier_multiplier": {
            1: 0.58,
            2: 0.78,
            3: 0.9,
            4: 1.08,
        },
        "critical_required_skill_penalty": 8,
    },
    "evidence": {
        "action_weight": 0.20,
        "tool_weight": 0.22,
        "context_weight": 0.20,
        "metric_weight": 0.25,
        "scope_weight": 0.13,
        "tier_1_max": 45,
        "tier_2_min": 52,
        "tier_3_min": 66,
        "tier_4_min": 84,
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
        "shallow_keyword_penalty": 5,
    },
    "experience": {
        "title_alignment_weight": 0.30,
        "responsibility_weight": 0.24,
        "domain_weight": 0.16,
        "years_weight": 0.18,
        "evidence_weight": 0.12,
    },
    "projects": {
        "baseline_without_project_requirement": 78,
        "skill_overlap_weight": 0.46,
        "evidence_quality_weight": 0.36,
        "project_presence_weight": 0.18,
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
    "readability": {
        "base_parseability": 96,
        "short_preview_threshold": 12,
        "low_bullet_quality_penalty": 16,
        "icon_symbol_penalty": 6,
        "table_marker_penalty": 8,
        "required_sections": ["summary", "skills", "experience", "education"],
    },
    "stuffing": {
        "skill_repeat_warning": 6,
        "skill_repeat_strong_warning": 10,
        "phrase_repeat_warning": 4,
        "density_warning": 0.10,
        "density_strong_warning": 0.16,
        "max_penalty": 18,
    },
    "completeness": {
        "contact_weight": 0.28,
        "summary_weight": 0.20,
        "achievement_weight": 0.28,
        "section_weight": 0.24,
    },
    "calibration_caps": {
        "one_required_hard_skill_missing": 82,
        "multiple_required_hard_skills_missing": 72,
        "core_role_missing": 76,
        "years_mismatch": 78,
        "mostly_shallow_evidence": 84,
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
        return "Very Strong Match"
    if score >= 70:
        return "Strong Match"
    if score >= 55:
        return "Moderate Match"
    if score >= 40:
        return "Weak Match"
    return "Poor Match"


def legacy_score_label(score: int) -> str:
    label = score_label(score)
    if label == "Very Strong Match":
        return "Strong Match"
    if label == "Poor Match":
        return "Weak Match"
    return label
