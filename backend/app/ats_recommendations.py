from __future__ import annotations

from .ats_config import legacy_score_label


def build_explanation_panel(*, overall_score: int, parsing_confidence: float, strengths: list[str], risks: list[str]) -> dict[str, object]:
    label = legacy_score_label(overall_score)
    if label == "Strong Match":
        headline = "Your resume is broadly aligned with the target role."
    elif label == "Moderate Match":
        headline = "You have a credible match, but a few gaps are holding the score back."
    else:
        headline = "The role fit is currently weak and needs more direct evidence."

    parsing_note = (
        "Formatting looks ATS-safe."
        if parsing_confidence >= 0.85
        else "Formatting introduces some parse risk, so the score is being interpreted conservatively."
    )
    summary = " ".join(
        part for part in [headline, parsing_note, *(strengths[:1] if strengths else []), *(risks[:1] if risks else [])] if part
    )

    return {
        "headline": headline,
        "confidence_label": label,
        "summary": summary.strip(),
        "strengths": strengths[:4],
        "risks": risks[:4],
    }


def suggestion_for_missing_keyword(keyword: str, *, priority: str, issue_type: str = "content") -> dict[str, str]:
    return {
        "priority": priority,
        "title": f"Add clearer evidence for {keyword}",
        "details": f"The job description treats {keyword} as important, but the resume does not show enough direct evidence.",
        "issue_type": issue_type,
        "suggested_edit": f"If this matches your background, add a bullet that shows where you used {keyword}, what you built, and the measurable outcome.",
    }


def suggestion_for_formatting(issue: str, recommendation: str, *, priority: str = "medium") -> dict[str, str]:
    return {
        "priority": priority,
        "title": issue,
        "details": recommendation,
        "issue_type": "formatting",
        "suggested_edit": recommendation,
    }
