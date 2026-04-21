from __future__ import annotations

from .ats_evidence import TermAssessment
from .ats_role_matching import RoleMatchResult
from .job_description import JobDescriptionAnalysis


def build_suggestions(
    job: JobDescriptionAnalysis,
    job_breakdown: dict[str, int],
    readability_breakdown: dict[str, int],
    gap_analysis: dict[str, object],
    assessments: list[TermAssessment],
    formatting_issues: list[dict[str, str]],
    stuffing_warnings: list[dict[str, str]],
    role_match: RoleMatchResult,
) -> dict[str, list[dict[str, str]]]:
    grouped = {"high_impact": [], "medium_impact": [], "low_impact": []}

    for gap in gap_analysis["critical_gaps"][:3]:
        grouped["high_impact"].append(
            {
                "priority": "high",
                "title": gap["title"],
                "details": gap["details"],
                "issue_type": "content",
                "suggested_edit": "Address this only if it is accurate: add direct evidence in a summary line, experience bullet, project bullet, or certification entry.",
            }
        )

    weak_evidence = [item for item in assessments if item.is_matched and item.importance in {"high", "medium"} and item.evidence_tier <= 1]
    for item in weak_evidence[:3]:
        grouped["high_impact"].append(
            {
                "priority": "high",
                "title": f"Show real work evidence for {item.term}",
                "details": f"Your resume mentions {item.term}, but mainly in a skills/list context.",
                "issue_type": "content",
                "suggested_edit": f"If truthful, add a project or experience bullet showing how you used {item.term}, what you built, and the result.",
            }
        )

    for item in gap_analysis["missing_required_skills"][:3]:
        grouped["high_impact"].append(_keyword_suggestion(item["keyword"], "high", required=True))
    for item in gap_analysis["missing_preferred_skills"][:4]:
        grouped["medium_impact"].append(_keyword_suggestion(item["keyword"], "medium", required=False))

    if role_match.score < 72:
        grouped["medium_impact"].append(
            {
                "priority": "medium",
                "title": "Strengthen role alignment signals",
                "details": f"Role alignment is {role_match.score}/100, so the resume title or summary may not clearly map to {job.title}.",
                "issue_type": "content",
                "suggested_edit": "If accurate, align the headline, summary, or experience titles with the target role family without overstating seniority.",
            }
        )

    weakest_job = sorted(job_breakdown.items(), key=lambda item: item[1])[:2]
    for section_name, score in weakest_job:
        if score >= 74:
            continue
        grouped["medium_impact"].append(
            {
                "priority": "medium",
                "title": f"Improve {section_name.replace('_', ' ')}",
                "details": f"This job-match component is scoring {score}/100.",
                "issue_type": "content",
                "suggested_edit": _job_component_suggestion(section_name, job),
            }
        )

    for issue in formatting_issues[:2]:
        grouped["medium_impact"].append(
            {
                "priority": issue["severity"],
                "title": issue["issue"],
                "details": issue["details"],
                "issue_type": "formatting",
                "suggested_edit": issue["recommendation"],
            }
        )

    for warning in stuffing_warnings[:2]:
        grouped["medium_impact"].append(
            {
                "priority": warning["severity"],
                "title": f"Reduce repetition of {warning['keyword']}",
                "details": warning["details"],
                "issue_type": "content",
                "suggested_edit": warning["recommendation"],
            }
        )

    weakest_readability = sorted(readability_breakdown.items(), key=lambda item: item[1])[:2]
    for section_name, score in weakest_readability:
        if score >= 80:
            continue
        grouped["low_impact"].append(
            {
                "priority": "low",
                "title": f"Polish {section_name.replace('_', ' ')}",
                "details": f"This readability component is scoring {score}/100.",
                "issue_type": "formatting",
                "suggested_edit": _readability_component_suggestion(section_name),
            }
        )

    return {key: _dedupe_suggestions(value)[:6] for key, value in grouped.items()}


def flatten_suggestions(grouped: dict[str, list[dict[str, str]]]) -> list[dict[str, str]]:
    return [*grouped.get("high_impact", []), *grouped.get("medium_impact", []), *grouped.get("low_impact", [])][:10]


def _keyword_suggestion(keyword: str, priority: str, *, required: bool) -> dict[str, str]:
    impact = "required" if required else "preferred"
    return {
        "priority": priority,
        "title": f"Add clearer evidence for {keyword}",
        "details": f"The JD treats {keyword} as a {impact} signal, but the resume does not show clear evidence.",
        "issue_type": "content",
        "suggested_edit": f"If you have used {keyword}, add it to a real project or experience bullet with action, context, and outcome. Do not add it if you have not used it.",
    }


def _job_component_suggestion(section_name: str, job: JobDescriptionAnalysis) -> str:
    if section_name == "skills_match":
        focus_terms = ", ".join(job.required_skills[:3]) or "the must-have tools"
        return f"Add truthful direct evidence for {focus_terms}, preferably in experience or projects instead of only the skills list."
    if section_name == "experience_relevance":
        return "Rewrite one or two bullets to mirror the JD responsibilities with action, tool, business context, and a measurable result."
    if section_name == "keyword_coverage":
        return "Use JD language naturally across summary, projects, and work bullets; avoid repeating raw keyword lists."
    if section_name == "projects_relevance":
        return "If you have relevant project work, add a concise bullet naming the stack, what you built, and the result or scope."
    if section_name == "seniority_years_match":
        return "Clarify dates and scope of ownership; do not inflate years, but make actual experience easy to parse."
    if section_name == "role_alignment":
        return "If accurate, align the headline and recent role descriptions to the target role family."
    return "Add concise, truthful evidence that maps directly to the target job requirement."


def _readability_component_suggestion(section_name: str) -> str:
    if section_name == "bullet_clarity":
        return "Prefer bullets that start with an action verb and include tool, scope, and measurable result where truthful."
    if section_name == "section_completeness":
        return "Restore standard sections with enough plain text for ATS systems to parse."
    if section_name == "date_consistency":
        return "Use one consistent date format throughout experience and education."
    if section_name == "contact_info_presence":
        return "Keep email, phone, and location as selectable plain text near the top."
    return "Use simple section headings and plain text reading order for reliable parsing."


def _dedupe_suggestions(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for item in items:
        key = item["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique
