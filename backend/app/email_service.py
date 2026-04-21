from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
from pathlib import Path


class EmailDeliveryError(RuntimeError):
    pass


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _load_local_env() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    project_dir = backend_dir.parent
    _load_env_file(project_dir / ".env")
    _load_env_file(backend_dir / ".env")


def _smtp_config() -> dict[str, object]:
    _load_local_env()
    host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.getenv("SMTP_PORT", "587").strip() or "587")
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASS", "")
    sender = os.getenv("SMTP_FROM", user).strip()

    if "gmail.com" in host.lower():
        password = password.replace(" ", "")

    if not user or not password or not sender:
        raise EmailDeliveryError("SMTP_USER, SMTP_PASS, and SMTP_FROM must be configured.")

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "sender": sender,
    }


def _sender_header(sender: str) -> str:
    name, address = parseaddr(sender)
    if name and address:
        return formataddr((name, address))
    return sender


def _send_email(*, to_email: str, subject: str, text_body: str, html_body: str) -> None:
    config = _smtp_config()
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = _sender_header(str(config["sender"]))
    message["To"] = to_email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(str(config["host"]), int(config["port"]), timeout=20) as server:
            server.starttls(context=context)
            server.login(str(config["user"]), str(config["password"]))
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError("Email could not be delivered.") from exc


def send_signup_otp(to_email: str, otp_code: str) -> None:
    text_body = (
        "Welcome to ResuME.\n\n"
        f"Your account verification code is {otp_code}.\n"
        "This code expires in 10 minutes.\n\n"
        "If you did not request this, you can ignore this email."
    )
    html_body = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6;color:#111827">
      <h2 style="margin:0 0 12px">Verify your ResuME account</h2>
      <p>Your account verification code is:</p>
      <p style="font-size:28px;font-weight:700;letter-spacing:4px;margin:16px 0">{otp_code}</p>
      <p>This code expires in 10 minutes.</p>
      <p>If you did not request this, you can ignore this email.</p>
    </div>
    """
    _send_email(
        to_email=to_email,
        subject="Verify your ResuME account",
        text_body=text_body,
        html_body=html_body,
    )


def send_welcome_email(to_email: str) -> None:
    text_body = (
        "Welcome to ResuME!\n\n"
        "Your account is verified. You can now save resume profiles, export PDFs, and run ATS checks from your workspace."
    )
    html_body = """
    <div style="font-family:Arial,sans-serif;line-height:1.6;color:#111827">
      <h2 style="margin:0 0 12px">Welcome to ResuME</h2>
      <p>Your account is verified.</p>
      <p>You can now save resume profiles, export PDFs, and run ATS checks from your workspace.</p>
    </div>
    """
    _send_email(
        to_email=to_email,
        subject="Welcome to ResuME",
        text_body=text_body,
        html_body=html_body,
    )


def send_password_reset_otp(to_email: str, otp_code: str) -> None:
    text_body = (
        "You requested a ResuME password reset.\n\n"
        f"Your password reset code is {otp_code}.\n"
        "This code expires in 10 minutes.\n\n"
        "If you did not request this, you can ignore this email."
    )
    html_body = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6;color:#111827">
      <h2 style="margin:0 0 12px">Reset your ResuME password</h2>
      <p>Your password reset code is:</p>
      <p style="font-size:28px;font-weight:700;letter-spacing:4px;margin:16px 0">{otp_code}</p>
      <p>This code expires in 10 minutes.</p>
      <p>If you did not request this, you can ignore this email.</p>
    </div>
    """
    _send_email(
        to_email=to_email,
        subject="Reset your ResuME password",
        text_body=text_body,
        html_body=html_body,
    )
