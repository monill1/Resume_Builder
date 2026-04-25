from __future__ import annotations

import io
import re

from fastapi import HTTPException, UploadFile
from pydantic import ValidationError

from .ats_normalization import dedupe_preserve_order, extract_known_terms
from .models import Basics, CertificationItem, EducationItem, ExperienceItem, ProjectItem, ResumePayload, SkillCategory

MAX_PDF_BYTES = 8 * 1024 * 1024
SECTION_ALIASES = {
    "summary": "summary",
    "profile": "summary",
    "professional summary": "summary",
    "objective": "summary",
    "skills": "skills",
    "technical skills": "skills",
    "core skills": "skills",
    "experience": "experience",
    "work experience": "experience",
    "professional experience": "experience",
    "employment": "experience",
    "projects": "projects",
    "project experience": "projects",
    "education": "education",
    "certifications": "certifications",
    "certification": "certifications",
    "licenses": "certifications",
}
SECTION_KEYS = ["summary", "skills", "experience", "projects", "education", "certifications"]
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[A-Za-z]{2,24})+\b")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
YEAR_RE = re.compile(r"(?:19|20)\d{2}")
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/[^\s,;]+", re.IGNORECASE)
GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[^\s,;]+", re.IGNORECASE)


async def uploaded_pdf_to_resume(upload: UploadFile) -> ResumePayload:
    filename = upload.filename or ""
    if upload.content_type not in {"application/pdf", "application/x-pdf"} and not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Upload a PDF resume file.")

    pdf_bytes = await upload.read(MAX_PDF_BYTES + 1)
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF file is too large. Upload a file smaller than 8 MB.")

    text = extract_pdf_text(pdf_bytes)
    if len(text) < 80:
        raise HTTPException(status_code=422, detail="Could not extract enough readable text from this PDF. Scanned image PDFs are not supported yet.")

    try:
        return resume_from_pdf_text(text)
    except ValidationError as exc:
        message = exc.errors()[0].get("msg", "invalid extracted resume data")
        raise HTTPException(status_code=422, detail=f"Could not convert this PDF into ATS-readable resume data: {message}") from exc


def extract_pdf_text(pdf_bytes: bytes) -> str:
    extracted_text = _extract_pdf_text_with_pypdf(pdf_bytes)
    if extracted_text:
        return normalize_pdf_text(extracted_text)

    extracted_text = _extract_pdf_text_with_pymupdf(pdf_bytes)
    if extracted_text:
        return normalize_pdf_text(extracted_text)

    raise HTTPException(
        status_code=500,
        detail="PDF text extraction is not available. Install pypdf or PyMuPDF in the Python environment running the backend.",
    )


def _extract_pdf_text_with_pypdf(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages[:8])
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Unable to read this PDF. Try exporting the resume as a text-based PDF.") from exc


def _extract_pdf_text_with_pymupdf(pdf_bytes: bytes) -> str:
    try:
        import fitz
    except ImportError:
        return ""

    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
            return "\n".join(page.get_text("text") or "" for page in document[:8])
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Unable to read this PDF. Try exporting the resume as a text-based PDF.") from exc


def resume_from_pdf_text(text: str) -> ResumePayload:
    lines = [line.strip(" \t•*-") for line in text.splitlines() if line.strip(" \t•*-")]
    sections = split_resume_sections(lines)
    fallback_body = "\n".join(lines[1:]) if len(lines) > 1 else text
    summary_lines = sections.get("summary") or first_content_lines(lines)
    skills_text = "\n".join(sections.get("skills") or [])
    experience_lines = sections.get("experience") or sections.get("projects") or first_content_lines(lines, limit=12)
    education_lines = sections.get("education") or []
    certification_lines = sections.get("certifications") or []
    name = extract_name(lines)
    email = extract_email(text)
    phone = extract_phone(text)
    location = extract_location(lines)

    skill_terms = extract_known_terms(skills_text or fallback_body, categories={"hard_skill", "soft_skill", "domain", "certification"})
    skills = [SkillCategory(name="Extracted Skills", items=skill_terms[:30])] if skill_terms else []

    summary = compact_text(" ".join(summary_lines), min_chars=30)
    experience = build_experience(experience_lines, fallback_body)
    projects = build_projects(sections.get("projects") or [])
    education = build_education(education_lines)
    certifications = build_certifications(certification_lines)

    return ResumePayload(
        basics=Basics(
            full_name=name,
            headline=infer_headline(lines, summary)[:120],
            email=email,
            phone=phone,
            location=location,
            linkedin=extract_link(text, LINKEDIN_RE),
            github=extract_link(text, GITHUB_RE),
            summary=summary,
        ),
        skills=skills,
        experience=experience,
        projects=projects,
        education=education,
        certifications=certifications,
        section_order=SECTION_KEYS,
    )


def normalize_pdf_text(text: str) -> str:
    normalized = text.replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def split_resume_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {key: [] for key in SECTION_KEYS}
    current: str | None = None
    for line in lines:
        heading = normalize_heading(line)
        if heading in SECTION_ALIASES:
            current = SECTION_ALIASES[heading]
            continue
        if current:
            sections[current].append(line)
    return {key: value for key, value in sections.items() if value}


def normalize_heading(line: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z &]", "", line).strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned if len(cleaned.split()) <= 3 else ""


def extract_name(lines: list[str]) -> str:
    for line in lines[:8]:
        if EMAIL_RE.search(line) or PHONE_RE.search(line) or "linkedin" in line.lower() or "github" in line.lower():
            continue
        words = re.findall(r"[A-Za-z][A-Za-z'.-]+", line)
        if 2 <= len(words) <= 5:
            return " ".join(words)[:80]
    return "Uploaded Resume"


def extract_email(text: str) -> str:
    match = EMAIL_RE.search(text)
    return match.group(0).strip(" .,:;|") if match else "uploaded.resume@example.com"


def extract_phone(text: str) -> str:
    match = PHONE_RE.search(text)
    if not match:
        return "+10000000000"
    phone = re.sub(r"\s+", " ", match.group(0)).strip()
    return phone[:25]


def extract_location(lines: list[str]) -> str:
    for line in lines[:10]:
        if EMAIL_RE.search(line) or PHONE_RE.search(line):
            continue
        if "," in line and len(line) <= 80:
            return line[:100]
    return "Not specified"


def extract_link(text: str, pattern: re.Pattern[str]) -> str | None:
    match = pattern.search(text)
    if not match:
        return None
    value = match.group(0).rstrip(".,)")
    normalized = value if value.startswith("http") else f"https://{value}"
    return normalized[:2083] if "." in normalized else None


def infer_headline(lines: list[str], summary: str) -> str:
    for line in lines[1:8]:
        if EMAIL_RE.search(line) or PHONE_RE.search(line) or "linkedin" in line.lower():
            continue
        if 3 <= len(line) <= 120:
            return line
    return summary[:117] + "..." if len(summary) > 120 else summary


def first_content_lines(lines: list[str], limit: int = 6) -> list[str]:
    content = []
    for line in lines[1:]:
        if EMAIL_RE.search(line) or PHONE_RE.search(line) or normalize_heading(line) in SECTION_ALIASES:
            continue
        content.append(line)
        if len(content) >= limit:
            break
    return content


def compact_text(text: str, min_chars: int = 0) -> str:
    compacted = re.sub(r"\s+", " ", text).strip()
    if len(compacted) >= min_chars:
        return compacted[:900]
    return (compacted + " Resume content extracted from uploaded PDF for ATS scoring.").strip()[:900]


def build_experience(lines: list[str], fallback_body: str) -> list[ExperienceItem]:
    bullets = meaningful_bullets(lines) or meaningful_bullets(fallback_body.splitlines())
    bullets = bullets[:8] or ["Resume experience content extracted from uploaded PDF for ATS comparison."]
    role = infer_role_from_lines(lines) or "Resume Experience"
    years = YEAR_RE.findall("\n".join(lines))
    start = years[0] if years else "2024"
    end = years[-1] if len(years) > 1 else None
    return [
        ExperienceItem(
            company="Uploaded PDF",
            role=role[:80],
            location="Not specified",
            start_date=start,
            end_date=end,
            current=end is None,
            achievements=bullets,
        )
    ]


def build_projects(lines: list[str]) -> list[ProjectItem]:
    bullets = meaningful_bullets(lines)
    if not bullets:
        return []
    return [
        ProjectItem(
            name="Uploaded PDF Projects",
            tech_stack=(", ".join(extract_known_terms("\n".join(lines), categories={"hard_skill", "domain"})[:8]) or "Extracted from resume")[:120],
            highlights=bullets[:5],
        )
    ]


def build_education(lines: list[str]) -> list[EducationItem]:
    if not lines:
        return []
    text = " | ".join(lines[:4])
    year_match = YEAR_RE.search(text)
    return [
        EducationItem(
            institution=(lines[0] or "Education")[:120],
            degree=(lines[1] if len(lines) > 1 else "Degree details extracted from PDF")[:120],
            duration=year_match.group(0) if year_match else "Not specified",
        )
    ]


def build_certifications(lines: list[str]) -> list[CertificationItem]:
    certs = []
    for line in lines[:5]:
        if len(line) < 2:
            continue
        year = YEAR_RE.search(line)
        certs.append(CertificationItem(title=line[:120], issuer="Uploaded PDF", year=year.group(0) if year else ""))
    return certs


def meaningful_bullets(lines: list[str]) -> list[str]:
    bullets = []
    for line in lines:
        cleaned = compact_text(line)
        if not is_resume_evidence_line(cleaned):
            continue
        bullets.append(cleaned[:260])
    return dedupe_preserve_order(bullets)


def is_resume_evidence_line(text: str) -> bool:
    if len(text) < 32 or normalize_heading(text) in SECTION_ALIASES:
        return False
    lowered = text.lower()
    if EMAIL_RE.search(text) or PHONE_RE.search(text):
        return False
    if re.fullmatch(r"[\w\s().,&/-]{2,80}", text) and not re.search(
        r"\b(built|created|developed|designed|implemented|managed|led|optimized|automated|improved|delivered|trained|analyzed|deployed|integrated|configured|reduced|increased|generated|documented|collaborated)\b",
        lowered,
    ):
        return False
    if re.search(r"\b(remote|hyderabad|india|software engineer|developer|internship|freelance|present)\b", lowered) and len(text.split()) <= 8:
        return False
    return True


def infer_role_from_lines(lines: list[str]) -> str | None:
    for line in lines[:8]:
        if YEAR_RE.search(line):
            line = YEAR_RE.split(line)[0].strip(" |-")
        if 3 <= len(line) <= 80:
            return line
    return None
