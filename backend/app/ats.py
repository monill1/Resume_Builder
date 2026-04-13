from __future__ import annotations

from .ats_scoring import score_resume
from .job_description import JobSourceContent, build_job_source, parse_job_description
from .models import ATSAnalysisResponse, ResumePayload
from .resume_parser import parse_resume


def prepare_job_source(*, job_url: str | None, job_description: str | None, target_title: str | None) -> JobSourceContent:
    return build_job_source(job_url=job_url, pasted_description=job_description, target_title=target_title)


def analyze_resume_against_job(resume: ResumePayload, job_source: JobSourceContent) -> ATSAnalysisResponse:
    job_analysis = parse_job_description(job_source)
    resume_analysis = parse_resume(resume)
    scoring_payload = score_resume(job_analysis, resume_analysis)
    return ATSAnalysisResponse(
        job_url=job_source.job_url,
        job_title=job_analysis.title,
        job_source=job_source.source,
        source_note=job_source.source_note,
        **scoring_payload,
    )
