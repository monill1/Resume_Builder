from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException

from .ats_normalization import clean_phrase, dedupe_preserve_order, extract_known_terms, top_term_frequencies


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
HTML_TITLE_PATTERN = re.compile(r"(?is)<title[^>]*>(.*?)</title>")
META_PATTERN_TEMPLATE = r'(?is)<meta[^>]+{attribute}\s*=\s*["\']{name}["\'][^>]+content\s*=\s*["\'](.*?)["\']'
TAG_RE = re.compile(r"(?is)<[^>]+>")
SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style|noscript|svg).*?>.*?</\1>")
COMMENT_RE = re.compile(r"(?is)<!--.*?-->")
LINE_SPLIT_RE = re.compile(r"\n+|[•\u2022]+")
YEARS_RE = re.compile(r"(\d+)\s*(?:\+|plus)?\s+years?(?:\s+of)?\s+experience", re.IGNORECASE)
DEGREE_RE = re.compile(
    r"(bachelor(?:'s)?|master(?:'s)?|phd|doctorate|b\.?tech|b\.?e\.?|m\.?tech|mba|bs|ba|ms)",
    re.IGNORECASE,
)
CERTIFICATION_RE = re.compile(r"([A-Z][A-Za-z0-9 +/&-]{2,80}(?:certification|certificate|certified|license|licensed))")
LOCATION_RE = re.compile(r"\b(remote|hybrid|onsite|on-site|relocation|located in [a-z ,]+)\b", re.IGNORECASE)
AUTH_RE = re.compile(r"\b(work authorization|authorized to work|visa|sponsorship|citizen|citizenship)\b", re.IGNORECASE)


@dataclass(frozen=True)
class JobSourceContent:
    source: str
    job_url: str | None
    title: str
    description: str
    text: str
    source_note: str | None = None


@dataclass(frozen=True)
class JobDescriptionAnalysis:
    source: JobSourceContent
    title: str
    required_skills: list[str]
    preferred_skills: list[str]
    tools: list[str]
    years_required: int | None
    degree_requirements: list[str]
    certifications: list[str]
    industry_keywords: list[str]
    action_phrases: list[str]
    responsibility_phrases: list[str]
    location_requirements: list[str]
    authorization_requirements: list[str]


def build_job_source(*, job_url: str | None, pasted_description: str | None, target_title: str | None) -> JobSourceContent:
    fallback_description = (pasted_description or "").strip()
    fallback_title = (target_title or "").strip()

    if job_url:
        try:
            fetched = fetch_job_posting(job_url)
            return JobSourceContent(
                source="url",
                job_url=job_url,
                title=fetched.title or fallback_title or "Job Posting",
                description=fetched.description,
                text=fetched.text,
            )
        except HTTPException as exc:
            if not fallback_description:
                raise exc
            return JobSourceContent(
                source="pasted_fallback",
                job_url=job_url,
                title=fallback_title or "Pasted Job Description",
                description=fallback_description,
                text=fallback_description,
                source_note=f"{exc.detail} Used your pasted description instead.",
            )

    if not fallback_description:
        raise HTTPException(status_code=422, detail="Provide a public job URL or paste a job description to run ATS analysis.")

    return JobSourceContent(
        source="pasted_description",
        job_url=None,
        title=fallback_title or _guess_title_from_text(fallback_description),
        description=fallback_description,
        text=fallback_description,
    )


def fetch_job_posting(job_url: str) -> JobSourceContent:
    request = Request(job_url, headers=REQUEST_HEADERS)
    try:
        with urlopen(request, timeout=15) as response:
            payload = response.read(1_000_000)
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                raise HTTPException(status_code=422, detail="This link did not return a readable HTML job page.")
            charset = response.headers.get_content_charset() or "utf-8"
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Unable to fetch the job page right now ({exc.code}).") from exc
    except URLError as exc:
        raise HTTPException(status_code=502, detail="Unable to reach that job link from the backend.") from exc

    html = payload.decode(charset, errors="ignore")
    title = _extract_meta_content(html, "property", "og:title") or _extract_title(html)
    description = (
        _extract_meta_content(html, "name", "description")
        or _extract_meta_content(html, "property", "og:description")
        or ""
    )
    text = _html_to_text(html)
    if len((title + " " + description + " " + text).strip()) < 220:
        raise HTTPException(
            status_code=422,
            detail="Could not extract enough job details from that link. Paste the job description to continue.",
        )
    return JobSourceContent(source="url", job_url=job_url, title=title or "Job Posting", description=description, text=text)


def parse_job_description(source: JobSourceContent) -> JobDescriptionAnalysis:
    combined_text = "\n".join(part for part in [source.title, source.description, source.text] if part).strip()
    lines = _to_lines(combined_text)
    required_lines = [
        line
        for line in lines
        if _line_matches_any(line, ("required", "must have", "qualification", "requirements"))
        and not _line_matches_any(line, ("preferred", "nice to have", "bonus", "plus", "ideal"))
    ]
    preferred_lines = [line for line in lines if _line_matches_any(line, ("preferred", "nice to have", "bonus", "plus", "ideal"))]
    responsibility_lines = [
        line
        for line in lines
        if _line_matches_any(line, ("responsib", "you will", "you'll", "what you'll do", "what you will do"))
        or _looks_like_responsibility(line)
    ]

    qualification_pool = "\n".join(required_lines or lines)
    preferred_pool = "\n".join(preferred_lines)
    all_text = combined_text

    required_skills = extract_known_terms(qualification_pool, categories={"hard_skill", "soft_skill"}) or extract_known_terms(
        source.title + "\n" + combined_text, categories={"hard_skill", "soft_skill"}
    )[:10]
    preferred_skills = [
        term for term in extract_known_terms(preferred_pool, categories={"hard_skill", "soft_skill"}) if term not in required_skills
    ]
    tools = extract_known_terms(all_text, categories={"hard_skill"})[:14]

    return JobDescriptionAnalysis(
        source=source,
        title=clean_phrase(source.title) or _guess_title_from_text(source.text),
        required_skills=required_skills,
        preferred_skills=preferred_skills,
        tools=tools,
        years_required=_extract_years(required_lines or lines),
        degree_requirements=_extract_degree_requirements(required_lines or lines),
        certifications=_extract_certifications(lines),
        industry_keywords=_extract_industry_keywords(source.title, all_text, required_skills + preferred_skills),
        action_phrases=_extract_action_phrases(responsibility_lines),
        responsibility_phrases=dedupe_preserve_order(responsibility_lines)[:8],
        location_requirements=_extract_regex_group(lines, LOCATION_RE),
        authorization_requirements=_extract_regex_group(lines, AUTH_RE),
    )


def _extract_title(html: str) -> str:
    match = HTML_TITLE_PATTERN.search(html)
    return _clean_text(match.group(1)) if match else ""


def _extract_meta_content(html: str, attribute: str, name: str) -> str:
    pattern = re.compile(META_PATTERN_TEMPLATE.format(attribute=attribute, name=re.escape(name)))
    match = pattern.search(html)
    return _clean_text(match.group(1)) if match else ""


def _html_to_text(html: str) -> str:
    stripped = COMMENT_RE.sub(" ", html)
    stripped = SCRIPT_STYLE_RE.sub(" ", stripped)
    stripped = TAG_RE.sub("\n", stripped)
    return _clean_text(stripped)


def _clean_text(text: str) -> str:
    text = unescape(text or "")
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _guess_title_from_text(text: str) -> str:
    lines = _to_lines(text)
    for line in lines[:4]:
        if 5 <= len(line) <= 100 and not _line_matches_any(line, ("responsib", "requirement", "qualification", "about", "team")):
            return line
    return "Target Role"


def _to_lines(text: str) -> list[str]:
    raw_lines = LINE_SPLIT_RE.split(text or "")
    expanded: list[str] = []
    for raw_line in raw_lines:
        for fragment in re.split(r"(?<=[.;])\s+(?=[A-Z])", raw_line):
            cleaned = clean_phrase(fragment)
            if cleaned:
                expanded.append(cleaned)
    return dedupe_preserve_order(expanded)


def _line_matches_any(line: str, markers: tuple[str, ...]) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in markers)


def _looks_like_responsibility(line: str) -> bool:
    lowered = line.lower()
    return lowered.startswith(("build", "develop", "design", "deliver", "lead", "own", "partner", "analyze", "create", "manage"))


def _extract_years(lines: list[str]) -> int | None:
    years: list[int] = []
    for line in lines:
        for match in YEARS_RE.findall(line):
            years.append(int(match))
    return max(years) if years else None


def _extract_degree_requirements(lines: list[str]) -> list[str]:
    degrees: list[str] = []
    for line in lines:
        if not _line_matches_any(line, ("degree", "bachelor", "master", "phd", "mba", "graduate")):
            continue
        degrees.extend(match.group(0) for match in DEGREE_RE.finditer(line))
    return dedupe_preserve_order(degrees)


def _extract_certifications(lines: list[str]) -> list[str]:
    certifications: list[str] = []
    for line in lines:
        certifications.extend(match.group(1) for match in CERTIFICATION_RE.finditer(line))
        if "certification" in line.lower() or "license" in line.lower():
            certifications.append(line)
    return dedupe_preserve_order(certifications)[:8]


def _extract_industry_keywords(title: str, text: str, excluded_terms: list[str]) -> list[str]:
    domain_terms = extract_known_terms(text, categories={"domain"})
    frequent_terms = top_term_frequencies(f"{title} {text}", limit=10)
    blocked = {
        *{term.lower() for term in excluded_terms},
        "required",
        "requirement",
        "requirements",
        "qualification",
        "qualifications",
        "preferred",
        "strong",
        "experience",
        "responsibilities",
        "responsibility",
        "developer",
        "engineer",
        "analyst",
        "build",
        "team",
    }
    return dedupe_preserve_order(domain_terms + [term for term in frequent_terms if term.lower() not in blocked])[:8]


def _extract_action_phrases(lines: list[str]) -> list[str]:
    phrases: list[str] = []
    for line in lines:
        if len(line.split()) < 4:
            continue
        phrases.append(line[:120])
    return dedupe_preserve_order(phrases)[:8]


def _extract_regex_group(lines: list[str], pattern: re.Pattern[str]) -> list[str]:
    matches: list[str] = []
    for line in lines:
        for match in pattern.finditer(line):
            matches.append(match.group(0))
    return dedupe_preserve_order(matches)
