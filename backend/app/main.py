from __future__ import annotations

import os
import logging

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .ats import analyze_resume_against_job, prepare_job_source
from .ats_optimizer import optimize_resume_against_job
from .database import (
    DatabaseUnavailableError,
    authenticate_user,
    clear_resume_drafts,
    create_resume_profile,
    create_session,
    create_user,
    delete_session,
    get_latest_resume_draft,
    get_user_by_session_token,
    init_db,
    list_resume_profiles,
    save_ats_analysis,
    save_ats_optimization,
    save_pdf_export,
    save_resume_draft,
)
from .models import (
    ATSAnalysisRequest,
    ATSAnalysisResponse,
    ATSOptimizeRequest,
    ATSOptimizeResponse,
    AuthCredentials,
    AuthSessionResponse,
    AuthUserResponse,
    ResumeProfileCreateRequest,
    ResumeProfileResponse,
    ResumeProfilesResponse,
    ResumeClearResponse,
    ResumeGenerateRequest,
    ResumeSaveRequest,
    ResumeSaveResponse,
    SampleResumeResponse,
    SavedResumeResponse,
)
from .pdf_generator import build_resume_pdf
from .sample_data import SAMPLE_RESUME

logger = logging.getLogger(__name__)


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


def _raise_database_error(exc: Exception) -> None:
    detail = str(exc) or "Database operation failed."
    raise HTTPException(status_code=503, detail=detail) from exc


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Sign in is required.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Invalid authorization header.")
    return token.strip()


def _session_payload(user: dict[str, object], token: str) -> AuthSessionResponse:
    return AuthSessionResponse(token=token, user=AuthUserResponse(**user))


def get_current_user(authorization: str | None = Header(default=None)) -> dict[str, object]:
    token = _extract_bearer_token(authorization)
    try:
        user = get_user_by_session_token(token)
    except Exception as exc:
        _raise_database_error(exc)

    if not user:
        raise HTTPException(status_code=401, detail="Your session has expired. Sign in again.")
    return user


@app.on_event("startup")
def startup() -> None:
    try:
        init_db()
    except DatabaseUnavailableError as exc:
        logger.warning("Database initialization skipped: %s", exc)
    except Exception as exc:
        logger.warning("Database initialization failed: %s", exc)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/sample", response_model=SampleResumeResponse)
def get_sample_resume() -> SampleResumeResponse:
    return SampleResumeResponse(resume=SAMPLE_RESUME)


@app.post("/api/auth/signup", response_model=AuthSessionResponse)
def sign_up(payload: AuthCredentials) -> AuthSessionResponse:
    try:
        user = create_user(payload.email, payload.password)
        token = create_session(int(user["id"]))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        _raise_database_error(exc)

    return _session_payload(user, token)


@app.post("/api/auth/login", response_model=AuthSessionResponse)
def sign_in(payload: AuthCredentials) -> AuthSessionResponse:
    try:
        user = authenticate_user(payload.email, payload.password)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        token = create_session(int(user["id"]))
    except HTTPException:
        raise
    except Exception as exc:
        _raise_database_error(exc)

    return _session_payload(user, token)


@app.get("/api/auth/me", response_model=AuthUserResponse)
def get_me(current_user: dict[str, object] = Depends(get_current_user)) -> AuthUserResponse:
    return AuthUserResponse(**current_user)


@app.post("/api/auth/logout")
def log_out(authorization: str | None = Header(default=None)) -> dict[str, str]:
    token = _extract_bearer_token(authorization)
    try:
        delete_session(token)
    except Exception as exc:
        _raise_database_error(exc)
    return {"status": "ok"}


@app.get("/api/resume/profiles", response_model=ResumeProfilesResponse)
def get_resume_profiles(current_user: dict[str, object] = Depends(get_current_user)) -> ResumeProfilesResponse:
    try:
        profiles = list_resume_profiles(int(current_user["id"]))
    except Exception as exc:
        _raise_database_error(exc)

    return ResumeProfilesResponse(profiles=[ResumeProfileResponse(**profile) for profile in profiles])


@app.post("/api/resume/profiles", response_model=ResumeProfileResponse)
def create_profile(
    payload: ResumeProfileCreateRequest,
    current_user: dict[str, object] = Depends(get_current_user),
) -> ResumeProfileResponse:
    try:
        profile = create_resume_profile(int(current_user["id"]), payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        _raise_database_error(exc)

    return ResumeProfileResponse(**profile)


@app.get("/api/resume/latest", response_model=SavedResumeResponse)
def get_latest_saved_resume(
    profile_id: int | None = None,
    current_user: dict[str, object] = Depends(get_current_user),
) -> SavedResumeResponse:
    try:
        latest = get_latest_resume_draft(int(current_user["id"]), profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        _raise_database_error(exc)

    return SavedResumeResponse(**latest) if latest else SavedResumeResponse()


@app.post("/api/resume/save", response_model=ResumeSaveResponse)
def save_resume(payload: ResumeSaveRequest, current_user: dict[str, object] = Depends(get_current_user)) -> ResumeSaveResponse:
    try:
        saved = save_resume_draft(
            payload.resume,
            payload.template_id,
            payload.section_color,
            int(current_user["id"]),
            payload.profile_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        _raise_database_error(exc)

    return ResumeSaveResponse(**saved)


@app.delete("/api/resume/saved", response_model=ResumeClearResponse)
def clear_saved_resumes(
    profile_id: int | None = None,
    current_user: dict[str, object] = Depends(get_current_user),
) -> ResumeClearResponse:
    try:
        deleted_count = clear_resume_drafts(int(current_user["id"]), profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        _raise_database_error(exc)

    return ResumeClearResponse(deleted_count=deleted_count)


@app.post("/api/resume/generate")
def generate_resume(payload: ResumeGenerateRequest, current_user: dict[str, object] = Depends(get_current_user)) -> Response:
    pdf_bytes = build_resume_pdf(payload.resume, payload.template_id, payload.section_color)
    filename = f"{payload.resume.basics.full_name.strip().replace(' ', '_')}_resume.pdf"
    try:
        save_pdf_export(
            resume=payload.resume,
            template_id=payload.template_id,
            section_color=payload.section_color,
            filename=filename,
            pdf_bytes=pdf_bytes,
            user_id=int(current_user["id"]),
            profile_id=payload.profile_id,
        )
        save_resume_draft(
            payload.resume,
            payload.template_id,
            payload.section_color,
            int(current_user["id"]),
            payload.profile_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        _raise_database_error(exc)

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@app.post("/api/ats/analyze", response_model=ATSAnalysisResponse)
def analyze_ats_match(
    payload: ATSAnalysisRequest,
    current_user: dict[str, object] = Depends(get_current_user),
) -> ATSAnalysisResponse:
    job_source = prepare_job_source(
        job_url=str(payload.job_url) if payload.job_url else None,
        job_description=payload.job_description,
        target_title=payload.target_title,
    )
    analysis = analyze_resume_against_job(payload.resume, job_source)
    try:
        save_ats_analysis(
            resume=payload.resume,
            analysis=analysis,
            job_url=str(payload.job_url) if payload.job_url else None,
            target_title=payload.target_title,
            job_description=payload.job_description,
            user_id=int(current_user["id"]),
            profile_id=payload.profile_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        _raise_database_error(exc)

    return analysis


@app.post("/api/ats/optimize", response_model=ATSOptimizeResponse)
def optimize_ats_resume(
    payload: ATSOptimizeRequest,
    current_user: dict[str, object] = Depends(get_current_user),
) -> ATSOptimizeResponse:
    job_source = prepare_job_source(
        job_url=str(payload.job_url) if payload.job_url else None,
        job_description=payload.job_description,
        target_title=payload.target_title,
    )
    optimization = optimize_resume_against_job(
        payload.resume,
        job_source,
        target_score=payload.target_score,
    )
    try:
        save_ats_optimization(
            original_resume=payload.resume,
            optimized_resume=optimization.optimized_resume,
            optimization=optimization,
            job_url=str(payload.job_url) if payload.job_url else None,
            target_title=payload.target_title,
            job_description=payload.job_description,
            user_id=int(current_user["id"]),
            profile_id=payload.profile_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        _raise_database_error(exc)

    return optimization
