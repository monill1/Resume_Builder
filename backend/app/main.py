from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .ats import analyze_resume_against_job, prepare_job_source
from .models import ATSAnalysisRequest, ATSAnalysisResponse, ResumeGenerateRequest, SampleResumeResponse
from .pdf_generator import build_resume_pdf
from .sample_data import SAMPLE_RESUME


def _allowed_origins() -> list[str]:
    configured = os.getenv("ALLOWED_ORIGINS", "")
    origins = [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]
    if origins:
        return origins
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]


app = FastAPI(title="ATS Resume Builder API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/sample", response_model=SampleResumeResponse)
def get_sample_resume() -> SampleResumeResponse:
    return SampleResumeResponse(resume=SAMPLE_RESUME)


@app.post("/api/resume/generate")
def generate_resume(payload: ResumeGenerateRequest) -> Response:
    pdf_bytes = build_resume_pdf(payload.resume, payload.template_id)
    filename = f"{payload.resume.basics.full_name.strip().replace(' ', '_')}_resume.pdf"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@app.post("/api/ats/analyze", response_model=ATSAnalysisResponse)
def analyze_ats_match(payload: ATSAnalysisRequest) -> ATSAnalysisResponse:
    job_source = prepare_job_source(
        job_url=str(payload.job_url) if payload.job_url else None,
        job_description=payload.job_description,
        target_title=payload.target_title,
    )
    return analyze_resume_against_job(payload.resume, job_source)
