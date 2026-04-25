from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _normalize_url(value: object) -> object:
    if not isinstance(value, str):
        return value

    trimmed = value.strip()
    if not trimmed:
        return None

    if "://" not in trimmed:
        return f"https://{trimmed}"

    return trimmed


def _normalize_hex_color(value: object) -> object:
    if value is None:
        return None
    if not isinstance(value, str):
        return value

    trimmed = value.strip()
    if not trimmed:
        return None
    if not HEX_COLOR_RE.fullmatch(trimmed):
        raise ValueError("Color must be a valid 6-digit hex value like #1C5FDB.")
    return trimmed.lower()


class Basics(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=80)
    headline: str = Field(default="", max_length=120)
    email: EmailStr
    phone: str = Field(..., min_length=7, max_length=25)
    location: str = Field(..., min_length=2, max_length=100)
    linkedin: Optional[HttpUrl] = None
    github: Optional[HttpUrl] = None
    website: Optional[HttpUrl] = None
    photo: Optional[str] = Field(default=None, max_length=2_000_000)
    photo_offset_y: int = Field(default=0, ge=-40, le=40)
    summary: str = Field(..., min_length=30, max_length=900)

    _normalize_linkedin = field_validator("linkedin", mode="before")(_normalize_url)
    _normalize_github = field_validator("github", mode="before")(_normalize_url)
    _normalize_website = field_validator("website", mode="before")(_normalize_url)

    @field_validator("photo", mode="before")
    @classmethod
    def _normalize_photo(cls, value: object) -> object:
        if not isinstance(value, str):
            return None if value is None else value
        trimmed = value.strip()
        if not trimmed:
            return None
        return trimmed if trimmed.startswith("data:image/") else None

    @field_validator("photo_offset_y", mode="before")
    @classmethod
    def _normalize_photo_offset_y(cls, value: object) -> object:
        if value is None or value == "":
            return 0
        if isinstance(value, (int, float)):
            return max(-40, min(40, int(round(value))))
        if isinstance(value, str):
            try:
                return max(-40, min(40, int(round(float(value.strip())))))
            except ValueError:
                return 0
        return value


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
    year: str = Field(default="", max_length=20)
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
    year: str = Field(default="", max_length=20)

    @field_validator("year", mode="before")
    @classmethod
    def _blank_year_to_empty_string(cls, value: object) -> object:
        return "" if value is None else value


SectionKey = Literal["summary", "skills", "experience", "projects", "education", "certifications"]
TemplateId = Literal[
    "classic-professional",
    "contemporary-accent",
    "executive-elegance",
    "profile-banner",
]


class ResumeLayoutOptions(BaseModel):
    executive_certifications_in_sidebar: bool = False


class ResumePayload(BaseModel):
    basics: Basics
    skills: List[SkillCategory] = Field(default_factory=list)
    experience: List[ExperienceItem] = Field(default_factory=list)
    projects: List[ProjectItem] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    certifications: List[CertificationItem] = Field(default_factory=list)
    layout_options: ResumeLayoutOptions = Field(default_factory=ResumeLayoutOptions)
    section_order: List[SectionKey] = Field(
        default_factory=lambda: ["summary", "skills", "experience", "projects", "education", "certifications"]
    )


class ResumeGenerateRequest(BaseModel):
    profile_id: Optional[int] = Field(default=None, gt=0)
    template_id: TemplateId = "classic-professional"
    section_color: Optional[str] = Field(default=None, max_length=7)
    resume: ResumePayload

    _normalize_section_color = field_validator("section_color", mode="before")(_normalize_hex_color)


class AuthCredentials(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class AuthOtpStartResponse(BaseModel):
    status: str
    message: str


class AuthOtpVerifyRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class AuthPasswordResetRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class AuthPasswordResetConfirmRequest(AuthOtpVerifyRequest):
    password: str = Field(..., min_length=8, max_length=128)


class AuthUserResponse(BaseModel):
    id: int
    email: EmailStr
    created_at: Optional[str] = None


class AuthSessionResponse(BaseModel):
    token: str
    user: AuthUserResponse


class PaymentPlanResponse(BaseModel):
    id: Literal["single_pdf", "monthly_pack"]
    label: str
    amount_paise: int
    currency: str
    download_credits: int
    valid_days: Optional[int] = None


class PaymentStatusResponse(BaseModel):
    exempt: bool
    remaining_downloads: int
    active_pack_expires_at: Optional[str] = None
    plans: List[PaymentPlanResponse] = Field(default_factory=list)


class PaymentOrderRequest(BaseModel):
    plan: Literal["single_pdf", "monthly_pack"]


class PaymentOrderResponse(BaseModel):
    key_id: str
    order_id: str
    amount_paise: int
    currency: str
    plan: Literal["single_pdf", "monthly_pack"]
    label: str
    description: str
    customer_email: EmailStr


class PaymentVerifyRequest(BaseModel):
    razorpay_order_id: str = Field(..., min_length=5, max_length=80)
    razorpay_payment_id: str = Field(..., min_length=5, max_length=80)
    razorpay_signature: str = Field(..., min_length=20, max_length=200)


class PaymentVerifyResponse(BaseModel):
    status: str
    message: str
    payment: PaymentStatusResponse


class ResumeProfileCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        if isinstance(value, str):
            return " ".join(value.strip().split())
        return value


class ResumeProfileResponse(BaseModel):
    id: int
    name: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    latest_saved_at: Optional[str] = None
    has_saved_draft: bool = False


class ResumeProfilesResponse(BaseModel):
    profiles: List[ResumeProfileResponse] = Field(default_factory=list)


class ResumeSaveRequest(BaseModel):
    profile_id: Optional[int] = Field(default=None, gt=0)
    template_id: TemplateId = "classic-professional"
    section_color: Optional[str] = Field(default=None, max_length=7)
    resume: dict[str, Any]

    _normalize_section_color = field_validator("section_color", mode="before")(_normalize_hex_color)


class ResumeSaveResponse(BaseModel):
    id: int
    profile_id: Optional[int] = None
    saved_at: Optional[str] = None


class SavedResumeResponse(BaseModel):
    id: Optional[int] = None
    profile_id: Optional[int] = None
    template_id: Optional[str] = None
    section_color: Optional[str] = None
    resume: Optional[dict[str, Any]] = None
    saved_at: Optional[str] = None


class ResumeClearResponse(BaseModel):
    deleted_count: int


class SampleResumeResponse(BaseModel):
    resume: ResumePayload


class ATSAnalysisRequest(BaseModel):
    profile_id: Optional[int] = Field(default=None, gt=0)
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
    match_type: Literal["exact", "alias", "phrase", "fuzzy", "related", "semantic"]
    source_sections: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    evidence_tier: int = Field(default=0, ge=0, le=4)
    evidence_quality: int = Field(default=0, ge=0, le=100)


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


class ATSSkillEvidence(BaseModel):
    keyword: str
    evidence_tier: int = Field(..., ge=0, le=4)
    evidence_quality: int = Field(..., ge=0, le=100)
    source_sections: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)


class ATSMissingRoleSignal(BaseModel):
    signal: str
    details: str
    severity: Literal["high", "medium", "low"]


class ATSStuffingWarning(BaseModel):
    severity: Literal["high", "medium", "low"]
    keyword: str
    details: str
    recommendation: str


class ATSSuggestionsByPriority(BaseModel):
    high_impact: List[ATSImprovementSuggestion] = Field(default_factory=list)
    medium_impact: List[ATSImprovementSuggestion] = Field(default_factory=list)
    low_impact: List[ATSImprovementSuggestion] = Field(default_factory=list)


class ATSScoreBreakdown(BaseModel):
    job_match: Dict[str, int] = Field(default_factory=dict)
    ats_readability: Dict[str, int] = Field(default_factory=dict)
    weights: Dict[str, float] = Field(default_factory=dict)
    job_match_weights: Dict[str, float] = Field(default_factory=dict)


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
    overall_ats_score: int = Field(..., ge=0, le=100)
    job_match_score: int = Field(..., ge=0, le=100)
    ats_readability_score: int = Field(..., ge=0, le=100)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    confidence_factors: Dict[str, float] = Field(default_factory=dict)
    confidence_label: Literal["Strong Match", "Moderate Match", "Weak Match"]
    match_quality_label: Literal["Very Strong Match", "Strong Match", "Moderate Match", "Weak Match", "Poor Match"]
    parsing_confidence: float = Field(..., ge=0.0, le=1.0)
    score_cap_applied: bool = False
    score_cap_reason: Optional[str] = None
    score_caps_applied: List[Dict[str, Any]] = Field(default_factory=list)
    detected_role_family: str = ""
    detected_resume_role_family: str = ""
    weight_profile_name: str = ""
    weight_profile_used: Dict[str, float] = Field(default_factory=dict)
    matched_requirements: List[Dict[str, Any]] = Field(default_factory=list)
    weakly_matched_requirements: List[Dict[str, Any]] = Field(default_factory=list)
    unmatched_requirements: List[Dict[str, Any]] = Field(default_factory=list)
    matched_responsibilities: List[Dict[str, Any]] = Field(default_factory=list)
    missing_responsibilities: List[Dict[str, Any]] = Field(default_factory=list)
    semantic_requirement_matches: List[Dict[str, Any]] = Field(default_factory=list)
    semantic_coverage: int = Field(default=0, ge=0, le=100)
    matched_concepts: List[Dict[str, Any]] = Field(default_factory=list)
    partial_concepts: List[Dict[str, Any]] = Field(default_factory=list)
    missing_concepts: List[Dict[str, Any]] = Field(default_factory=list)
    semantic_model_name: str = ""
    semantic_model_available: bool = False
    responsibility_match_score: int = Field(default=0, ge=0, le=100)
    summary: str
    section_scores: ATSSectionScores
    score_breakdown: ATSScoreBreakdown
    missing_keywords: List[ATSKeywordGap] = Field(default_factory=list)
    missing_required_skills: List[ATSKeywordGap] = Field(default_factory=list)
    missing_preferred_skills: List[ATSKeywordGap] = Field(default_factory=list)
    missing_role_signals: List[ATSMissingRoleSignal] = Field(default_factory=list)
    missing_education_certifications: List[ATSKeywordGap] = Field(default_factory=list)
    matched_keywords: List[ATSKeywordMatch] = Field(default_factory=list)
    matched_skills: List[ATSKeywordMatch] = Field(default_factory=list)
    strong_evidence_skills: List[ATSSkillEvidence] = Field(default_factory=list)
    weak_evidence_skills: List[ATSSkillEvidence] = Field(default_factory=list)
    formatting_issues: List[ATSFormattingIssue] = Field(default_factory=list)
    critical_gaps: List[ATSCriticalGap] = Field(default_factory=list)
    stuffing_warnings: List[ATSStuffingWarning] = Field(default_factory=list)
    suggestions: ATSSuggestionsByPriority = Field(default_factory=ATSSuggestionsByPriority)
    improvement_suggestions: List[ATSImprovementSuggestion] = Field(default_factory=list)
    parse_preview: str
    comparison_view: List[ATSComparisonItem] = Field(default_factory=list)
    explanation_panel: ATSExplanationPanel
    analyzed_resume: Optional[ResumePayload] = None


class AutoFixEdit(BaseModel):
    section: Literal["headline", "summary", "skills", "experience", "projects", "education", "certifications"]
    target_id: str
    original_text: str
    new_text: str
    keywords_addressed: List[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    expected_score_impact: int = 0


class AutoFixUnresolvedItem(BaseModel):
    keyword: str
    importance: Literal["high", "medium", "low"]
    reason: str
    preferred_section: Optional[str] = None


class AutoFixPlan(BaseModel):
    headline_edits: List[AutoFixEdit] = Field(default_factory=list)
    summary_edits: List[AutoFixEdit] = Field(default_factory=list)
    skill_edits: List[AutoFixEdit] = Field(default_factory=list)
    experience_bullet_edits: List[AutoFixEdit] = Field(default_factory=list)
    project_bullet_edits: List[AutoFixEdit] = Field(default_factory=list)
    education_edits: List[AutoFixEdit] = Field(default_factory=list)
    certification_edits: List[AutoFixEdit] = Field(default_factory=list)
    unresolved_items: List[AutoFixUnresolvedItem] = Field(default_factory=list)
    reasoning: List[str] = Field(default_factory=list)
    estimated_impact: dict[str, int] = Field(default_factory=dict)
    updated_sections: List[str] = Field(default_factory=list)


class ATSOptimizeRequest(ATSAnalysisRequest):
    target_score: int = Field(default=85, ge=60, le=100)
    latest_analysis: Optional[ATSAnalysisResponse] = None


class ATSOptimizeResponse(BaseModel):
    optimized_resume: ResumePayload
    analysis: ATSAnalysisResponse
    previous_score: int = Field(..., ge=0, le=100)
    updated_score: int = Field(..., ge=0, le=100)
    score_delta: int
    target_score: int = Field(..., ge=60, le=100)
    target_reached: bool = False
    applied_changes: List[str] = Field(default_factory=list)
    remaining_gaps: List[str] = Field(default_factory=list)
    safety_note: str
    fix_plan: AutoFixPlan = Field(default_factory=AutoFixPlan)
