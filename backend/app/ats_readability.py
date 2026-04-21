from __future__ import annotations

import re
from dataclasses import dataclass

from .ats_config import ATS_SCORING_CONFIG
from .ats_evidence import TermAssessment, average_bullet_quality
from .ats_normalization import normalize_text
from .resume_parser import ResumeAnalysis


SYMBOL_RE = re.compile(r"[★✓●■◆➤→↳]")
TABLE_MARKER_RE = re.compile(r"\|{2,}|\t{2,}")


@dataclass(frozen=True)
class ReadabilityResult:
    score: int
    sub_scores: dict[str, int]
    parsing_confidence: float
    formatting_issues: list[dict[str, str]]
    stuffing_warnings: list[dict[str, str]]
    repetition_penalty: int


def score_readability(resume: ResumeAnalysis, assessments: list[TermAssessment]) -> ReadabilityResult:
    config = ATS_SCORING_CONFIG
    sub_scores = {
        "section_completeness": _section_completeness(resume),
        "section_heading_detection": _heading_detection(resume),
        "parseability": _parseability(resume),
        "bullet_clarity": _bullet_clarity(resume),
        "contact_info_presence": _contact_info(resume),
        "date_consistency": _date_consistency(resume),
        "tables_icons_symbols": _tables_icons_symbols(resume),
        "repetition_stuffing": 100,
    }
    stuffing_warnings, repetition_penalty = detect_stuffing(resume, assessments)
    sub_scores["repetition_stuffing"] = max(0, 100 - round(repetition_penalty * 4.5))
    score = round(sum(config["readability_weights"][key] * value for key, value in sub_scores.items()))

    formatting_issues = _formatting_issues(resume, sub_scores)
    parsing_confidence = _confidence_from_readability(score, formatting_issues, stuffing_warnings)
    return ReadabilityResult(
        score=max(0, min(100, score)),
        sub_scores=sub_scores,
        parsing_confidence=parsing_confidence,
        formatting_issues=formatting_issues,
        stuffing_warnings=stuffing_warnings,
        repetition_penalty=repetition_penalty,
    )


def detect_stuffing(resume: ResumeAnalysis, assessments: list[TermAssessment]) -> tuple[list[dict[str, str]], int]:
    config = ATS_SCORING_CONFIG["stuffing"]
    warnings: list[dict[str, str]] = []
    penalty = 0
    word_count = max(1, len(normalize_text(resume.parse_preview).split()))

    for item in assessments:
        if not item.is_matched or item.occurrence_count < config["skill_repeat_warning"]:
            continue
        if item.evidence_tier >= 3 and item.occurrence_count < config["skill_repeat_strong_warning"]:
            continue
        severity = "high" if item.occurrence_count >= config["skill_repeat_strong_warning"] else "medium"
        extra = item.occurrence_count - config["skill_repeat_warning"] + 1
        shallow = item.evidence_tier <= 1
        penalty += extra * (3 if severity == "high" else 2)
        if shallow:
            penalty += 3
        warnings.append(
            {
                "severity": severity,
                "keyword": item.term,
                "details": f"{item.term} appears {item.occurrence_count} times, but the evidence is not proportionally strong.",
                "recommendation": "Keep the keyword where it is truthful and replace repetition with one stronger action/result bullet.",
            }
        )

    repeated_phrases = _repeated_phrases(resume.parse_preview)
    for phrase, count in repeated_phrases[:3]:
        penalty += (count - config["phrase_repeat_warning"] + 1) * 2
        warnings.append(
            {
                "severity": "medium",
                "keyword": phrase,
                "details": f"The phrase '{phrase}' appears repeatedly.",
                "recommendation": "Vary the wording and focus repeated concepts into concise, evidence-backed bullets.",
            }
        )

    keyword_mentions = sum(item.occurrence_count for item in assessments if item.is_matched and item.category == "hard_skill")
    density = keyword_mentions / word_count
    matched_skills = [item for item in assessments if item.is_matched and item.category == "hard_skill"]
    shallow_ratio = (
        sum(1 for item in matched_skills if item.evidence_tier <= 1) / len(matched_skills)
        if matched_skills
        else 1.0
    )
    if density >= config["density_warning"] and shallow_ratio >= 0.35:
        severity = "high" if density >= config["density_strong_warning"] else "medium"
        penalty += 6 if severity == "high" else 3
        warnings.append(
            {
                "severity": severity,
                "keyword": "keyword density",
                "details": f"Technical keyword density is about {round(density * 100, 1)}%, which can look unnatural if not backed by bullets.",
                "recommendation": "Favor fewer, stronger bullets that show tools, scope, and measurable outcomes.",
            }
        )

    return warnings[:6], min(config["max_penalty"], penalty)


def _section_completeness(resume: ResumeAnalysis) -> int:
    required = ATS_SCORING_CONFIG["readability"]["required_sections"]
    score = sum(1 for section in required if resume.standard_sections_present.get(section)) / len(required)
    optional_bonus = 0.08 if resume.standard_sections_present.get("projects") else 0.0
    return round(100 * min(1.0, score + optional_bonus))


def _heading_detection(resume: ResumeAnalysis) -> int:
    standard = ATS_SCORING_CONFIG["standard_sections"]
    present = sum(1 for section in standard if resume.standard_sections_present.get(section))
    return round(100 * (present / len(standard)))


def _parseability(resume: ResumeAnalysis) -> int:
    score = ATS_SCORING_CONFIG["readability"]["base_parseability"]
    if len(resume.parse_preview.splitlines()) < ATS_SCORING_CONFIG["readability"]["short_preview_threshold"]:
        score -= 18
    if resume.parse_warnings:
        score -= min(18, len(resume.parse_warnings) * 5)
    if TABLE_MARKER_RE.search(resume.parse_preview):
        score -= ATS_SCORING_CONFIG["readability"]["table_marker_penalty"]
    if SYMBOL_RE.search(resume.parse_preview):
        score -= ATS_SCORING_CONFIG["readability"]["icon_symbol_penalty"]
    return max(0, min(100, round(score)))


def _bullet_clarity(resume: ResumeAnalysis) -> int:
    lines = resume.section_lines.get("experience", []) + resume.section_lines.get("projects", [])
    quality = average_bullet_quality(lines)
    if not lines:
        return 35
    if quality <= 0:
        return 48
    return max(35, min(100, quality + 14))


def _contact_info(resume: ResumeAnalysis) -> int:
    required = ["email", "phone", "location"]
    base = sum(1 for key in required if resume.contact_signals.get(key)) / len(required)
    optional = 0.08 if resume.contact_signals.get("linkedin") or resume.contact_signals.get("github_or_website") else 0.0
    return round(100 * min(1.0, base + optional))


def _date_consistency(resume: ResumeAnalysis) -> int:
    if not resume.date_formats:
        return 72
    if len(resume.date_formats) == 1:
        return 100
    if resume.date_formats <= {"year_only", "month_year"}:
        return 82
    return 62


def _tables_icons_symbols(resume: ResumeAnalysis) -> int:
    score = 100
    if TABLE_MARKER_RE.search(resume.parse_preview):
        score -= 30
    symbol_count = len(SYMBOL_RE.findall(resume.parse_preview))
    if symbol_count:
        score -= min(28, symbol_count * 4)
    return max(0, score)


def _formatting_issues(resume: ResumeAnalysis, sub_scores: dict[str, int]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    missing_contact = [key for key in ("email", "phone", "location") if not resume.contact_signals.get(key)]
    if missing_contact:
        issues.append(
            {
                "severity": "high",
                "issue": "Missing contact details",
                "details": "ATS systems and recruiters expect email, phone, and location in clear text.",
                "recommendation": "Add missing contact details in the top section using plain text.",
            }
        )
    missing_standard = [
        section for section in ATS_SCORING_CONFIG["readability"]["required_sections"] if not resume.standard_sections_present.get(section)
    ]
    if missing_standard:
        issues.append(
            {
                "severity": "high",
                "issue": "Missing standard sections",
                "details": f"The resume is missing standard ATS sections: {', '.join(missing_standard)}.",
                "recommendation": "Use standard headings such as Summary, Skills, Experience, and Education.",
            }
        )
    if sub_scores["date_consistency"] < 90:
        issues.append(
            {
                "severity": "medium",
                "issue": "Inconsistent date formatting",
                "details": "Mixed date styles make timeline parsing less reliable.",
                "recommendation": "Use one date style consistently, such as `2024 - 2025` or `Jan 2024 - Mar 2025` throughout.",
            }
        )
    if sub_scores["parseability"] < 82:
        issues.append(
            {
                "severity": "medium",
                "issue": "Parseability risk",
                "details": "The plain-text reading order is short or contains structure that may parse less reliably.",
                "recommendation": "Keep sections in a clear top-to-bottom order and expand thin bullets with plain text.",
            }
        )
    if sub_scores["tables_icons_symbols"] < 90:
        issues.append(
            {
                "severity": "low",
                "issue": "Symbols or table-like formatting detected",
                "details": "Decorative symbols or table markers can reduce parse reliability in some ATS systems.",
                "recommendation": "Use simple text, standard bullets, and avoid table-like separators for important content.",
            }
        )
    return issues[:6]


def _confidence_from_readability(score: int, issues: list[dict[str, str]], stuffing_warnings: list[dict[str, str]]) -> float:
    confidence = score / 100
    confidence -= 0.025 * len(issues)
    confidence -= 0.02 * len(stuffing_warnings)
    return round(max(0.45, min(0.98, confidence)), 2)


def _repeated_phrases(text: str) -> list[tuple[str, int]]:
    tokens = [token for token in normalize_text(text).split() if len(token) > 3]
    counts: dict[str, int] = {}
    for index in range(max(0, len(tokens) - 2)):
        phrase = " ".join(tokens[index : index + 3])
        counts[phrase] = counts.get(phrase, 0) + 1
    threshold = ATS_SCORING_CONFIG["stuffing"]["phrase_repeat_warning"]
    return sorted([(phrase, count) for phrase, count in counts.items() if count >= threshold], key=lambda item: (-item[1], item[0]))
