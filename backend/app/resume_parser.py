from __future__ import annotations

import re
from dataclasses import dataclass

from .ats_config import ATS_SCORING_CONFIG
from .ats_normalization import dedupe_preserve_order, extract_known_terms
from .models import ResumePayload


DATE_YEAR_RE = re.compile(r"(?:19|20)\d{2}")
MONTH_HINT_RE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|january|february|march|april|june|july|august|september|october|november|december)\b",
    re.IGNORECASE,
)
METRIC_RE = re.compile(r"\b\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?(?:x|k|m|b)\b|\b\d+\b")


@dataclass(frozen=True)
class ResumeAnalysis:
    section_text: dict[str, str]
    section_lines: dict[str, list[str]]
    parse_preview: str
    experience_titles: list[str]
    experience_years: float
    keyword_inventory: dict[str, list[str]]
    measurable_achievement_count: int
    contact_signals: dict[str, bool]
    standard_sections_present: dict[str, bool]
    date_formats: set[str]
    parse_warnings: list[str]


def parse_resume(resume: ResumePayload) -> ResumeAnalysis:
    summary_text = f"{resume.basics.headline}\n{resume.basics.summary}".strip()
    skills_lines = [f"{skill.name}: {', '.join(skill.items)}" for skill in resume.skills if skill.name or skill.items]
    experience_lines: list[str] = []
    experience_titles: list[str] = []
    for item in resume.experience:
        experience_titles.append(item.role)
        experience_lines.append(
            " | ".join(
                part
                for part in [
                    item.role,
                    item.company,
                    item.location,
                    f"{item.start_date} - {'Present' if item.current else (item.end_date or '')}".strip(),
                ]
                if part
            )
        )
        experience_lines.extend(item.achievements)

    project_lines: list[str] = []
    for item in resume.projects:
        project_lines.append(" | ".join(part for part in [item.name, item.tech_stack, str(item.link or "")] if part))
        project_lines.extend(item.highlights)

    education_lines = [
        " | ".join(part for part in [item.institution, item.degree, item.duration, item.location or "", item.score or ""] if part)
        for item in resume.education
    ]
    certification_lines = [
        " | ".join(part for part in [item.title, item.issuer, item.year] if part) for item in resume.certifications
    ]

    section_text = {
        "summary": summary_text,
        "skills": "\n".join(skills_lines),
        "experience": "\n".join(line for line in experience_lines if line),
        "projects": "\n".join(line for line in project_lines if line),
        "education": "\n".join(line for line in education_lines if line),
        "certifications": "\n".join(line for line in certification_lines if line),
    }
    section_lines = {section: [line for line in text.splitlines() if line.strip()] for section, text in section_text.items()}
    parse_preview = _build_parse_preview(resume, section_lines)
    date_formats = _detect_date_formats(resume)
    parse_warnings = _detect_parse_warnings(resume, section_lines, date_formats)

    keyword_inventory = {
        section: extract_known_terms(text, categories={"hard_skill", "soft_skill", "domain", "certification"})
        for section, text in section_text.items()
    }
    experience_bullets = [bullet for item in resume.experience for bullet in item.achievements]
    project_bullets = [bullet for item in resume.projects for bullet in item.highlights]
    measurable_achievement_count = sum(1 for bullet in [*experience_bullets, *project_bullets] if METRIC_RE.search(bullet))
    contact_signals = {
        "email": bool(resume.basics.email),
        "phone": bool(resume.basics.phone),
        "location": bool(resume.basics.location),
        "linkedin": bool(resume.basics.linkedin),
        "github_or_website": bool(resume.basics.github or resume.basics.website),
    }
    standard_sections_present = {
        section: bool(section_lines.get(section))
        or (section == "summary" and bool(resume.basics.summary))
        for section in ATS_SCORING_CONFIG["standard_sections"]
    }

    return ResumeAnalysis(
        section_text=section_text,
        section_lines=section_lines,
        parse_preview=parse_preview,
        experience_titles=dedupe_preserve_order(experience_titles),
        experience_years=_estimate_experience_years(resume),
        keyword_inventory=keyword_inventory,
        measurable_achievement_count=measurable_achievement_count,
        contact_signals=contact_signals,
        standard_sections_present=standard_sections_present,
        date_formats=date_formats,
        parse_warnings=parse_warnings,
    )


def _build_parse_preview(resume: ResumePayload, section_lines: dict[str, list[str]]) -> str:
    lines = [
        resume.basics.full_name,
        resume.basics.headline,
        f"Email: {resume.basics.email}",
        f"Phone: {resume.basics.phone}",
        f"Location: {resume.basics.location}",
    ]
    for section_key in resume.section_order:
        normalized_lines = section_lines.get(section_key, [])
        if not normalized_lines:
            continue
        lines.append(section_key.upper())
        lines.extend(normalized_lines)
    return "\n".join(line for line in lines if line)


def _detect_date_formats(resume: ResumePayload) -> set[str]:
    formats: set[str] = set()
    values = [item.start_date for item in resume.experience] + [item.end_date or "" for item in resume.experience]
    values.extend(item.duration for item in resume.education)
    for value in values:
        if not value:
            continue
        has_year = bool(DATE_YEAR_RE.search(value))
        has_month = bool(MONTH_HINT_RE.search(value))
        if has_year and has_month:
            formats.add("month_year")
        elif has_year:
            formats.add("year_only")
        else:
            formats.add("other")
    return formats


def _detect_parse_warnings(resume: ResumePayload, section_lines: dict[str, list[str]], date_formats: set[str]) -> list[str]:
    warnings: list[str] = []
    if len(date_formats) > 1:
        warnings.append("Date formatting is inconsistent across experience or education entries.")
    if not resume.basics.email or not resume.basics.phone or not resume.basics.location:
        warnings.append("Contact details are incomplete, which lowers ATS parse reliability.")
    if resume.section_order[:2] not in (["summary", "skills"], ["summary", "experience"], ["skills", "experience"]):
        warnings.append("Section order is less standard than most ATS-safe resumes.")
    if len(section_lines.get("experience", [])) < 2:
        warnings.append("Experience content is thin, which makes skill evidence harder for ATS systems to extract.")
    if len(_build_parse_preview(resume, section_lines).splitlines()) < 12:
        warnings.append("Plain-text parse preview is short, which usually means important resume detail is missing.")
    return warnings


def _estimate_experience_years(resume: ResumePayload) -> float:
    total_years = 0.0
    current_year = 2026
    for item in resume.experience:
        years = [int(match.group(0)) for match in DATE_YEAR_RE.finditer(f"{item.start_date} {item.end_date or ''}")]
        if not years:
            continue
        start_year = min(years)
        end_year = current_year if item.current or not item.end_date else max(years)
        total_years += max(0.5, end_year - start_year + 0.25)
    return round(total_years, 1)
