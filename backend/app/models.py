from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator


def _normalize_url(value: object) -> object:
    if not isinstance(value, str):
        return value

    trimmed = value.strip()
    if not trimmed:
        return None

    if "://" not in trimmed:
        return f"https://{trimmed}"

    return trimmed


class Basics(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=80)
    headline: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(..., min_length=7, max_length=25)
    location: str = Field(..., min_length=2, max_length=100)
    linkedin: Optional[HttpUrl] = None
    github: Optional[HttpUrl] = None
    website: Optional[HttpUrl] = None
    summary: str = Field(..., min_length=30, max_length=900)

    _normalize_linkedin = field_validator("linkedin", mode="before")(_normalize_url)
    _normalize_github = field_validator("github", mode="before")(_normalize_url)
    _normalize_website = field_validator("website", mode="before")(_normalize_url)


class SkillCategory(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    items: List[str] = Field(default_factory=list)


class ExperienceItem(BaseModel):
    company: str = Field(..., min_length=2, max_length=80)
    company_link: Optional[HttpUrl] = None
    role: str = Field(..., min_length=2, max_length=80)
    location: str = Field(..., min_length=2, max_length=80)
    start_date: str = Field(..., min_length=2, max_length=30)
    end_date: Optional[str] = Field(default=None, max_length=30)
    current: bool = False
    achievements: List[str] = Field(default_factory=list)

    _normalize_company_link = field_validator("company_link", mode="before")(_normalize_url)


class ProjectItem(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    tech_stack: str = Field(..., min_length=2, max_length=120)
    link: Optional[HttpUrl] = None
    highlights: List[str] = Field(default_factory=list)

    _normalize_link = field_validator("link", mode="before")(_normalize_url)


class EducationItem(BaseModel):
    institution: str = Field(..., min_length=2, max_length=120)
    degree: str = Field(..., min_length=2, max_length=120)
    duration: str = Field(..., min_length=2, max_length=40)
    score: Optional[str] = Field(default=None, max_length=40)
    location: Optional[str] = Field(default=None, max_length=60)


class CertificationItem(BaseModel):
    title: str = Field(..., min_length=2, max_length=120)
    issuer: str = Field(..., min_length=2, max_length=80)
    year: str = Field(..., min_length=2, max_length=20)


SectionKey = Literal["summary", "skills", "experience", "projects", "education", "certifications"]
TemplateId = Literal[
    "classic-professional",
    "contemporary-accent",
]


class ResumePayload(BaseModel):
    basics: Basics
    skills: List[SkillCategory] = Field(default_factory=list)
    experience: List[ExperienceItem] = Field(default_factory=list)
    projects: List[ProjectItem] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    certifications: List[CertificationItem] = Field(default_factory=list)
    section_order: List[SectionKey] = Field(
        default_factory=lambda: ["summary", "skills", "experience", "projects", "education", "certifications"]
    )


class ResumeGenerateRequest(BaseModel):
    template_id: TemplateId = "classic-professional"
    resume: ResumePayload


class SampleResumeResponse(BaseModel):
    resume: ResumePayload


class ATSAnalysisRequest(BaseModel):
    job_url: Optional[HttpUrl] = None
    job_description: Optional[str] = Field(default=None, min_length=30, max_length=20000)
    target_title: Optional[str] = Field(default=None, max_length=140)
    resume: ResumePayload

    @field_validator("job_description", "target_title", mode="before")
    @classmethod
    def _blank_strings_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("job_url", mode="before")
    @classmethod
    def _blank_url_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("resume")
    @classmethod
    def _ensure_job_input_present(cls, resume_value: ResumePayload, info) -> ResumePayload:
        data = info.data
        if not data.get("job_url") and not data.get("job_description"):
            raise ValueError("Provide either a job URL or pasted job description.")
        return resume_value


class ATSSectionScores(BaseModel):
    skills_match: int = Field(..., ge=0, le=100)
    experience_relevance: int = Field(..., ge=0, le=100)
    keyword_coverage: int = Field(..., ge=0, le=100)
    education_certifications: int = Field(..., ge=0, le=100)
    formatting_parseability: int = Field(..., ge=0, le=100)
    completeness: int = Field(..., ge=0, le=100)


class ATSKeywordGap(BaseModel):
    keyword: str
    importance: Literal["high", "medium", "low"]
    category: str
    details: str


class ATSKeywordMatch(BaseModel):
    keyword: str
    importance: Literal["high", "medium", "low"]
    match_type: Literal["exact", "semantic"]
    source_sections: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)


class ATSFormattingIssue(BaseModel):
    severity: Literal["high", "medium", "low"]
    issue: str
    details: str
    recommendation: str


class ATSCriticalGap(BaseModel):
    title: str
    details: str
    impact: str


class ATSImprovementSuggestion(BaseModel):
    priority: Literal["high", "medium", "low"]
    title: str
    details: str
    issue_type: Literal["content", "formatting"]
    suggested_edit: Optional[str] = None


class ATSComparisonItem(BaseModel):
    requirement: str
    importance: Literal["high", "medium", "low"]
    status: Literal["matched", "partial", "missing"]
    evidence: List[str] = Field(default_factory=list)


class ATSExplanationPanel(BaseModel):
    headline: str
    confidence_label: Literal["Strong Match", "Moderate Match", "Weak Match"]
    summary: str
    strengths: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


class ATSAnalysisResponse(BaseModel):
    job_url: Optional[HttpUrl] = None
    job_title: str
    job_source: Literal["url", "pasted_description", "pasted_fallback"]
    source_note: Optional[str] = None
    overall_score: int = Field(..., ge=0, le=100)
    confidence_label: Literal["Strong Match", "Moderate Match", "Weak Match"]
    parsing_confidence: float = Field(..., ge=0.0, le=1.0)
    score_cap_applied: bool = False
    score_cap_reason: Optional[str] = None
    summary: str
    section_scores: ATSSectionScores
    missing_keywords: List[ATSKeywordGap] = Field(default_factory=list)
    matched_keywords: List[ATSKeywordMatch] = Field(default_factory=list)
    formatting_issues: List[ATSFormattingIssue] = Field(default_factory=list)
    critical_gaps: List[ATSCriticalGap] = Field(default_factory=list)
    improvement_suggestions: List[ATSImprovementSuggestion] = Field(default_factory=list)
    parse_preview: str
    comparison_view: List[ATSComparisonItem] = Field(default_factory=list)
    explanation_panel: ATSExplanationPanel
