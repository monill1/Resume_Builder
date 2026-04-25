from __future__ import annotations

import os
import logging
import secrets

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .ats import analyze_resume_against_job, prepare_job_source
from .ats_optimizer import optimize_resume_against_job
from .database import (
    DatabaseUnavailableError,
    authenticate_user,
    clear_resume_drafts,
    create_password_reset_otp,
    create_payment_order,
    create_resume_profile,
    create_session,
    create_signup_otp,
    delete_session,
    get_latest_resume_draft,
    get_payment_plan,
    get_payment_status,
    get_user_by_session_token,
    has_pdf_download_access,
    init_db,
    list_resume_profiles,
    complete_payment_order,
    consume_pdf_download_credit,
    reset_password_with_otp,
    save_ats_analysis,
    save_ats_optimization,
    save_pdf_export,
    save_resume_draft,
    verify_signup_otp,
)
from .email_service import EmailDeliveryError, send_password_reset_otp, send_signup_otp, send_welcome_email
from .payment_service import (
    PaymentConfigurationError,
    PaymentGatewayError,
    create_razorpay_order,
    get_razorpay_key_id,
    verify_razorpay_signature,
)
from .models import (
    ATSAnalysisRequest,
    ATSAnalysisResponse,
    ATSOptimizeRequest,
    ATSOptimizeResponse,
    AuthCredentials,
    AuthOtpStartResponse,
    AuthOtpVerifyRequest,
    AuthPasswordResetConfirmRequest,
    AuthPasswordResetRequest,
    AuthSessionResponse,
    AuthUserResponse,
    PaymentOrderRequest,
    PaymentOrderResponse,
    PaymentStatusResponse,
    PaymentVerifyRequest,
    PaymentVerifyResponse,
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
from .pdf_resume import uploaded_pdf_to_resume
from .sample_data import SAMPLE_RESUME
from .services.semantic_matcher import warm_semantic_model

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
    expose_headers=["Content-Disposition"],
)


def _raise_database_error(exc: Exception) -> None:
    detail = str(exc) or "Database operation failed."
    raise HTTPException(status_code=503, detail=detail) from exc


def _raise_email_error(exc: Exception) -> None:
    logger.warning("Email delivery failed: %s", exc)
    raise HTTPException(status_code=503, detail="Email could not be sent. Check SMTP configuration and try again.") from exc


def _raise_payment_error(exc: Exception) -> None:
    logger.warning("Payment gateway error: %s", exc)
    raise HTTPException(status_code=503, detail="Payment gateway is unavailable. Try again in a moment.") from exc


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Sign in is required.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Invalid authorization header.")
    return token.strip()


def _session_payload(user: dict[str, object], token: str) -> AuthSessionResponse:
    return AuthSessionResponse(token=token, user=AuthUserResponse(**user))


def _payment_status_payload(user: dict[str, object]) -> PaymentStatusResponse:
    status = get_payment_status(int(user["id"]), str(user["email"]))
    return PaymentStatusResponse(**status)


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
    try:
        warm_semantic_model()
    except Exception as exc:
        logger.warning("Semantic matcher model preload skipped: %s", exc)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/sample", response_model=SampleResumeResponse)
def get_sample_resume() -> SampleResumeResponse:
    return SampleResumeResponse(resume=SAMPLE_RESUME)


@app.post("/api/auth/signup", response_model=AuthOtpStartResponse)
def sign_up(payload: AuthCredentials) -> AuthOtpStartResponse:
    try:
        email, otp_code = create_signup_otp(payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        _raise_database_error(exc)

    try:
        send_signup_otp(email, otp_code)
    except EmailDeliveryError as exc:
        _raise_email_error(exc)

    return AuthOtpStartResponse(
        status="otp_sent",
        message="Verification code sent. Check your email to finish creating your account.",
    )


@app.post("/api/auth/signup/verify", response_model=AuthSessionResponse)
def verify_signup(payload: AuthOtpVerifyRequest) -> AuthSessionResponse:
    try:
        user = verify_signup_otp(payload.email, payload.otp)
        token = create_session(int(user["id"]))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        _raise_database_error(exc)

    try:
        send_welcome_email(str(user["email"]))
    except EmailDeliveryError as exc:
        logger.warning("Welcome email failed for user %s: %s", user["id"], exc)

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


@app.post("/api/auth/password/forgot", response_model=AuthOtpStartResponse)
def forgot_password(payload: AuthPasswordResetRequest) -> AuthOtpStartResponse:
    try:
        email, otp_code, should_send = create_password_reset_otp(payload.email)
    except Exception as exc:
        _raise_database_error(exc)

    if should_send:
        try:
            send_password_reset_otp(email, otp_code)
        except EmailDeliveryError as exc:
            _raise_email_error(exc)

    return AuthOtpStartResponse(
        status="otp_sent",
        message="If an account exists for this email, a password reset code has been sent.",
    )


@app.post("/api/auth/password/reset", response_model=AuthOtpStartResponse)
def reset_password(payload: AuthPasswordResetConfirmRequest) -> AuthOtpStartResponse:
    try:
        updated = reset_password_with_otp(payload.email, payload.otp, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        _raise_database_error(exc)

    if not updated:
        raise HTTPException(status_code=404, detail="Account was not found.")

    return AuthOtpStartResponse(status="password_reset", message="Password updated. Sign in with your new password.")


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


@app.get("/api/payments/status", response_model=PaymentStatusResponse)
def get_current_payment_status(current_user: dict[str, object] = Depends(get_current_user)) -> PaymentStatusResponse:
    try:
        return _payment_status_payload(current_user)
    except Exception as exc:
        _raise_database_error(exc)


@app.post("/api/payments/orders", response_model=PaymentOrderResponse)
def create_payment_checkout_order(
    payload: PaymentOrderRequest,
    current_user: dict[str, object] = Depends(get_current_user),
) -> PaymentOrderResponse:
    try:
        plan = get_payment_plan(payload.plan)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        _raise_database_error(exc)

    receipt = f"pdf-{current_user['id']}-{secrets.token_hex(8)}"
    try:
        razorpay_order = create_razorpay_order(
            amount_paise=int(plan["amount_paise"]),
            currency=str(plan["currency"]),
            receipt=receipt,
            notes={
                "user_id": str(current_user["id"]),
                "email": str(current_user["email"]),
                "plan": str(payload.plan),
            },
        )
    except PaymentConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PaymentGatewayError as exc:
        _raise_payment_error(exc)

    try:
        create_payment_order(
            user_id=int(current_user["id"]),
            plan=payload.plan,
            razorpay_order_id=str(razorpay_order["id"]),
            receipt=receipt,
        )
    except Exception as exc:
        _raise_database_error(exc)

    return PaymentOrderResponse(
        key_id=get_razorpay_key_id(),
        order_id=str(razorpay_order["id"]),
        amount_paise=int(plan["amount_paise"]),
        currency=str(plan["currency"]),
        plan=payload.plan,
        label=str(plan["label"]),
        description=(
            "Pay Rs. 20 for one PDF download."
            if payload.plan == "single_pdf"
            else "Pay Rs. 99 for 10 PDF downloads valid for 30 days."
        ),
        customer_email=str(current_user["email"]),
    )


@app.post("/api/payments/verify", response_model=PaymentVerifyResponse)
def verify_payment(
    payload: PaymentVerifyRequest,
    current_user: dict[str, object] = Depends(get_current_user),
) -> PaymentVerifyResponse:
    try:
        is_valid = verify_razorpay_signature(
            razorpay_order_id=payload.razorpay_order_id,
            razorpay_payment_id=payload.razorpay_payment_id,
            razorpay_signature=payload.razorpay_signature,
        )
    except PaymentConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not is_valid:
        raise HTTPException(status_code=400, detail="Payment verification failed.")

    try:
        status = complete_payment_order(
            user_id=int(current_user["id"]),
            razorpay_order_id=payload.razorpay_order_id,
            razorpay_payment_id=payload.razorpay_payment_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        _raise_database_error(exc)

    return PaymentVerifyResponse(
        status="paid",
        message="Payment verified. PDF download credits have been added.",
        payment=PaymentStatusResponse(**status),
    )


@app.post("/api/resume/generate")
def generate_resume(payload: ResumeGenerateRequest, current_user: dict[str, object] = Depends(get_current_user)) -> Response:
    user_id = int(current_user["id"])
    user_email = str(current_user["email"])
    try:
        if not has_pdf_download_access(user_id, user_email):
            raise HTTPException(status_code=402, detail="Payment is required before downloading a PDF.")
    except HTTPException:
        raise
    except Exception as exc:
        _raise_database_error(exc)

    try:
        pdf_bytes = build_resume_pdf(payload.resume, payload.template_id, payload.section_color)
    except Exception as exc:
        logger.exception("PDF generation failed.")
        raise HTTPException(status_code=500, detail="PDF generation failed.") from exc

    filename = f"{payload.resume.basics.full_name.strip().replace(' ', '_')}_resume.pdf"
    try:
        consume_pdf_download_credit(user_id, user_email)
        save_pdf_export(
            resume=payload.resume,
            template_id=payload.template_id,
            section_color=payload.section_color,
            filename=filename,
            pdf_bytes=pdf_bytes,
            user_id=user_id,
            profile_id=payload.profile_id,
        )
        save_resume_draft(
            payload.resume,
            payload.template_id,
            payload.section_color,
            user_id,
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


@app.post("/api/ats/analyze-pdf", response_model=ATSAnalysisResponse)
async def analyze_uploaded_pdf_match(
    job_url: str | None = Form(default=None),
    job_description: str | None = Form(default=None),
    target_title: str | None = Form(default=None),
    profile_id: int | None = Form(default=None),
    resume_pdf: UploadFile = File(...),
    current_user: dict[str, object] = Depends(get_current_user),
) -> ATSAnalysisResponse:
    try:
        resume = await uploaded_pdf_to_resume(resume_pdf)
        job_source = prepare_job_source(
            job_url=job_url,
            job_description=job_description,
            target_title=target_title,
        )
        analysis = analyze_resume_against_job(resume, job_source)
        analysis.analyzed_resume = resume
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Uploaded PDF ATS analysis failed.")
        raise HTTPException(status_code=422, detail=f"Unable to analyze this PDF resume: {exc}") from exc
    try:
        save_ats_analysis(
            resume=resume,
            analysis=analysis,
            job_url=job_url,
            target_title=target_title,
            job_description=job_description,
            user_id=int(current_user["id"]),
            profile_id=profile_id,
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
