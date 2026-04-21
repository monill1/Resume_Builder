from __future__ import annotations

from .ats_normalization import best_match_type, canonicalize_term, classify_term, clean_phrase, dedupe_preserve_order, is_strong_match_type, normalize_text
from .ats_scoring import score_resume
from .job_description import JobSourceContent, parse_job_description
from .models import ATSAnalysisResponse, ATSOptimizeResponse, ResumePayload
from .resume_parser import parse_resume

STANDARD_SECTION_ORDER = ["summary", "skills", "experience", "projects", "education", "certifications"]
BACKEND_TERMS = {"Python", "FastAPI", "Django", "Flask", "REST APIs", "SQL", "PostgreSQL", "Docker", "AWS"}
DATA_TERMS = {"Pandas", "NumPy", "Scikit-learn", "Machine Learning", "Natural Language Processing", "Generative AI"}


def optimize_resume_against_job(
    resume: ResumePayload,
    job_source: JobSourceContent,
    *,
    target_score: int = 85,
) -> ATSOptimizeResponse:
    job_analysis = parse_job_description(job_source)
    previous_analysis = _analyze_resume(resume, job_source, job_analysis)
    optimized_resume = resume.model_copy(deep=True)
    applied_changes: list[str] = []

    aggregate_text = _resume_text(resume)
    supported_terms = [term for term in _ordered_terms(job_analysis) if _supports_term(term, aggregate_text)]
    missing_supported_terms = [
        term
        for term in dedupe_preserve_order([*job_analysis.required_skills, *job_analysis.preferred_skills, *job_analysis.tools])
        if term not in _skill_inventory(optimized_resume) and _supports_term(term, aggregate_text) and classify_term(term) == "hard_skill"
    ]

    headline = _build_headline(optimized_resume, job_analysis, supported_terms)
    if headline and headline != optimized_resume.basics.headline:
        optimized_resume.basics.headline = headline
        applied_changes.append("Updated the headline with stronger role-aligned keywords already supported in the resume.")

    summary = _build_summary(optimized_resume, job_analysis, supported_terms)
    if summary and summary != clean_phrase(optimized_resume.basics.summary):
        optimized_resume.basics.summary = summary
        applied_changes.append("Rewrote the summary to reflect supported job keywords more clearly.")

    skills_changed = _apply_skill_updates(optimized_resume, job_analysis, missing_supported_terms)
    if skills_changed:
        applied_changes.append(skills_changed)

    exp_changes = _apply_entry_updates(optimized_resume.experience, supported_terms)
    if exp_changes:
        applied_changes.append(exp_changes)

    project_changes = _apply_project_updates(optimized_resume.projects, supported_terms)
    if project_changes:
        applied_changes.append(project_changes)

    optimized_resume.section_order = optimized_resume.section_order or STANDARD_SECTION_ORDER
    optimized_analysis = _analyze_resume(optimized_resume, job_source, job_analysis)

    if optimized_analysis.overall_score < previous_analysis.overall_score:
        return ATSOptimizeResponse(
            optimized_resume=resume,
            analysis=previous_analysis,
            previous_score=previous_analysis.overall_score,
            updated_score=previous_analysis.overall_score,
            score_delta=0,
            target_score=target_score,
            target_reached=previous_analysis.overall_score >= target_score,
            applied_changes=["No score-safe changes were applied. The current resume already reflects the strongest evidence the tool could place truthfully."],
            remaining_gaps=[item.keyword for item in previous_analysis.missing_keywords[:6]],
            safety_note="The optimizer kept the original resume because the tested rewrite reduced the ATS score.",
        )

    if not applied_changes:
        applied_changes = ["No score-safe changes were applied. The current resume already reflects the strongest evidence the tool could place truthfully."]

    return ATSOptimizeResponse(
        optimized_resume=optimized_resume,
        analysis=optimized_analysis,
        previous_score=previous_analysis.overall_score,
        updated_score=optimized_analysis.overall_score,
        score_delta=optimized_analysis.overall_score - previous_analysis.overall_score,
        target_score=target_score,
        target_reached=optimized_analysis.overall_score >= target_score,
        applied_changes=applied_changes,
        remaining_gaps=[item.keyword for item in optimized_analysis.missing_keywords[:6]],
        safety_note=_build_safety_note(previous_analysis.overall_score, optimized_analysis.overall_score),
    )


def _analyze_resume(resume: ResumePayload, job_source: JobSourceContent, job_analysis) -> ATSAnalysisResponse:
    resume_analysis = parse_resume(resume)
    scoring_payload = score_resume(job_analysis, resume_analysis)
    return ATSAnalysisResponse(
        job_url=job_source.job_url,
        job_title=job_analysis.title,
        job_source=job_source.source,
        source_note=job_source.source_note,
        **scoring_payload,
    )


def _ordered_terms(job_analysis) -> list[str]:
    return dedupe_preserve_order([
        *job_analysis.required_skills,
        *job_analysis.preferred_skills,
        *job_analysis.tools,
        *job_analysis.industry_keywords,
    ])


def _resume_text(resume: ResumePayload) -> str:
    return "\n".join(
        [
            resume.basics.headline,
            resume.basics.summary,
            *[f"{group.name}: {', '.join(group.items)}" for group in resume.skills],
            *["\n".join([item.role, item.company, *item.achievements]) for item in resume.experience],
            *["\n".join([item.name, item.tech_stack, *item.highlights]) for item in resume.projects],
            *[f"{item.degree} {item.institution}" for item in resume.education],
            *[f"{item.title} {item.issuer}" for item in resume.certifications],
        ]
    )


def _supports_term(term: str, text: str) -> bool:
    canonical = canonicalize_term(term)
    if is_strong_match_type(best_match_type(canonical, text)):
        return True
    normalized = normalize_text(text)
    if canonical == "REST APIs":
        return "api" in normalized and any(keyword.lower() in normalized for keyword in ("fastapi", "django", "backend"))
    if canonical == "AWS":
        return any(alias in normalized for alias in ("aws", "amazon web services", "ec2", "lambda", "s3"))
    if canonical == "Machine Learning":
        return any(alias in normalized for alias in ("ml", "machine learning", "model", "recommendation"))
    if canonical == "Natural Language Processing":
        return any(alias in normalized for alias in ("nlp", "transformers"))
    if canonical == "Generative AI":
        return any(alias in normalized for alias in ("llm", "genai", "generative ai", "transformers"))
    return False


def _build_headline(resume: ResumePayload, job_analysis, supported_terms: list[str]) -> str:
    current = clean_phrase(resume.basics.headline)
    if current and best_match_type(job_analysis.title, current):
        return current
    skill_terms = [term for term in supported_terms if classify_term(term) == "hard_skill"][:4]
    role = clean_phrase(job_analysis.title) or current or "Target Role"
    if skill_terms:
        return f"{role} | {', '.join(skill_terms)}"[:120].strip(" |,")
    return role[:120]


def _build_summary(resume: ResumePayload, job_analysis, supported_terms: list[str]) -> str:
    experience_years = parse_resume(resume).experience_years
    years_label = f"with about {max(1, round(experience_years))} years of experience" if experience_years else "with hands-on experience"
    role = clean_phrase(job_analysis.title) or clean_phrase(resume.basics.headline) or "Engineer"
    primary_terms = [term for term in supported_terms if classify_term(term) == "hard_skill"][:5]
    if not primary_terms:
        primary_terms = [term for term in _skill_inventory(resume) if term in BACKEND_TERMS or term in DATA_TERMS][:5]
    if primary_terms:
        lead = f"{role} {years_label} across {_list_to_sentence(primary_terms[:4])}."
    else:
        lead = f"{role} {years_label} building ATS-friendly backend and data solutions."
    if job_analysis.action_phrases:
        tail = clean_phrase(job_analysis.action_phrases[0])
    else:
        tail = "Focused on building reliable features and data-driven workflows"
    return _ensure_sentence(f"{lead} {tail}")[:900]


def _skill_inventory(resume: ResumePayload) -> set[str]:
    return {canonicalize_term(item) for group in resume.skills for item in group.items}


def _apply_skill_updates(resume: ResumePayload, job_analysis, missing_supported_terms: list[str]) -> str | None:
    if not missing_supported_terms:
        return None
    updated_groups = 0
    for term in missing_supported_terms[:6]:
        group_index = _best_skill_group_index(resume, term)
        if group_index is None:
            continue
        group = resume.skills[group_index]
        group.items = _prioritize_items(dedupe_preserve_order([*group.items, canonicalize_term(term)]), job_analysis)
        updated_groups += 1
    return f"Updated {updated_groups} skills area(s) to surface supported tools more clearly." if updated_groups else None


def _best_skill_group_index(resume: ResumePayload, term: str) -> int | None:
    canonical = canonicalize_term(term)
    for index, group in enumerate(resume.skills):
        group_name = normalize_text(group.name)
        if canonical in BACKEND_TERMS and any(token in group_name for token in ("backend", "api", "cloud", "tools")):
            return index
        if canonical in DATA_TERMS and any(token in group_name for token in ("data", "ml", "analytics")):
            return index
    return 0 if resume.skills else None


def _prioritize_items(items: list[str], job_analysis) -> list[str]:
    required = {canonicalize_term(term) for term in job_analysis.required_skills}
    preferred = {canonicalize_term(term) for term in [*job_analysis.preferred_skills, *job_analysis.tools]}
    return sorted(items, key=lambda item: (0 if canonicalize_term(item) in required else 1 if canonicalize_term(item) in preferred else 2, item.lower()))


def _apply_entry_updates(experience_items, supported_terms: list[str]) -> str | None:
    changed = 0
    for item in experience_items:
        entry_text = "\n".join([item.role, item.company, *item.achievements])
        relevant = [term for term in supported_terms if classify_term(term) != "domain" and _supports_term(term, entry_text)]
        if not relevant:
            continue
        for index, bullet in enumerate(item.achievements):
            updated = _enhance_bullet(bullet, relevant)
            if updated != bullet:
                item.achievements[index] = updated
                changed += 1
                break
        if changed == 2:
            break
    return f"Strengthened {changed} experience bullet(s) with clearer job-relevant evidence." if changed else None


def _apply_project_updates(project_items, supported_terms: list[str]) -> str | None:
    changed = 0
    for item in project_items:
        entry_text = "\n".join([item.name, item.tech_stack, *item.highlights])
        relevant = [term for term in supported_terms if classify_term(term) == "hard_skill" and _supports_term(term, entry_text)]
        if not relevant:
            continue
        for index, bullet in enumerate(item.highlights):
            updated = _enhance_bullet(bullet, relevant)
            if updated != bullet:
                item.highlights[index] = updated
                changed += 1
                break
        if changed == 1:
            break
    return f"Strengthened {changed} project bullet(s) with more relevant technical wording." if changed else None


def _enhance_bullet(bullet: str, terms: list[str]) -> str:
    sentence = clean_phrase(bullet)
    if not sentence:
        return sentence
    missing = [term for term in dedupe_preserve_order(terms) if not best_match_type(term, sentence)][:2]
    if not missing:
        return sentence
    addition = _list_to_sentence(missing)
    if "using" in sentence.lower() or "with" in sentence.lower():
        return _ensure_sentence(f"{sentence.rstrip('.')} and strengthened delivery with {addition}")
    return _ensure_sentence(f"{sentence.rstrip('.')} using {addition}")


def _list_to_sentence(items: list[str]) -> str:
    cleaned = [clean_phrase(item) for item in items if clean_phrase(item)]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def _ensure_sentence(text: str) -> str:
    sentence = clean_phrase(text)
    if not sentence:
        return ""
    if sentence.endswith((".", "!", "?")):
        return sentence
    return f"{sentence}."


def _build_safety_note(previous_score: int, updated_score: int) -> str:
    if updated_score > previous_score:
        return "The resume was updated with ATS-safe wording improvements based on evidence already present in the resume."
    return "The resume was updated only where the tool could safely preserve truthful claims. Remaining score gaps need stronger evidence, not new unsupported keywords."
