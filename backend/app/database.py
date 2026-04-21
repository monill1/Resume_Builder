from __future__ import annotations

import json
import os
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class DatabaseUnavailableError(RuntimeError):
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


def get_database_url() -> str:
    _load_local_env()
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise DatabaseUnavailableError("DATABASE_URL is not configured.")
    return database_url


def _import_psycopg():
    try:
        import psycopg
        from psycopg.rows import dict_row
        from psycopg.types.json import Jsonb
    except ImportError as exc:
        raise DatabaseUnavailableError(
            "PostgreSQL driver is missing. Run `pip install -r backend/requirements.txt`."
        ) from exc

    return psycopg, dict_row, Jsonb


def _connect(row_factory: Any | None = None):
    psycopg, _, _ = _import_psycopg()
    kwargs: dict[str, Any] = {}
    if row_factory is not None:
        kwargs["row_factory"] = row_factory
    return psycopg.connect(get_database_url(), **kwargs)


def _as_jsonb(value: dict[str, Any]):
    _, _, Jsonb = _import_psycopg()
    return Jsonb(value)


def _json_ready(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return json.loads(json.dumps(value, default=str))
    raise TypeError("Expected a Pydantic model or dictionary.")


def _resume_identity(resume_data: dict[str, Any]) -> tuple[str, str]:
    basics = resume_data.get("basics") if isinstance(resume_data.get("basics"), dict) else {}
    return str(basics.get("full_name") or "").strip(), str(basics.get("email") or "").strip()


def _profile_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "created_at": _iso_or_none(row.get("created_at")),
        "updated_at": _iso_or_none(row.get("updated_at")),
        "latest_saved_at": _iso_or_none(row.get("latest_saved_at")),
        "has_saved_draft": bool(row.get("has_saved_draft")),
    }


def _iso_or_none(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None


PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 310_000
OTP_TTL_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_PURPOSE_SIGNUP = "signup"
OTP_PURPOSE_PASSWORD_RESET = "password_reset"


def _hash_password(password: str) -> str:
    salt = secrets.token_urlsafe(24)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"{PASSWORD_HASH_ALGORITHM}${PASSWORD_HASH_ITERATIONS}${salt}${password_hash}"


def _generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_otp(email: str, purpose: str, code: str) -> str:
    normalized_code = "".join(character for character in code if character.isdigit())
    return hashlib.sha256(f"{email}:{purpose}:{normalized_code}".encode("utf-8")).hexdigest()


def _otp_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt, expected_hash = stored_hash.split("$", 3)
        if algorithm != PASSWORD_HASH_ALGORITHM:
            return False
        iterations = int(iterations_raw)
    except (TypeError, ValueError):
        return False

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return hmac.compare_digest(password_hash, expected_hash)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def init_db() -> None:
    with _connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_users (
                    id BIGSERIAL PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
                    token_hash TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_otps (
                    id BIGSERIAL PRIMARY KEY,
                    email TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    code_hash TEXT NOT NULL,
                    password_hash TEXT,
                    expires_at TIMESTAMPTZ NOT NULL,
                    consumed_at TIMESTAMPTZ,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_auth_otps_email_purpose_created
                ON auth_otps (email, purpose, created_at DESC);
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS resume_profiles (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (user_id, name)
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS resume_drafts (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES auth_users(id) ON DELETE CASCADE,
                    profile_id BIGINT REFERENCES resume_profiles(id) ON DELETE SET NULL,
                    full_name TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    template_id TEXT NOT NULL DEFAULT 'classic-professional',
                    section_color TEXT,
                    resume_data JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS pdf_exports (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES auth_users(id) ON DELETE CASCADE,
                    profile_id BIGINT REFERENCES resume_profiles(id) ON DELETE SET NULL,
                    full_name TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    template_id TEXT NOT NULL,
                    section_color TEXT,
                    filename TEXT NOT NULL,
                    resume_data JSONB NOT NULL,
                    pdf_bytes BYTEA NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ats_analyses (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES auth_users(id) ON DELETE CASCADE,
                    profile_id BIGINT REFERENCES resume_profiles(id) ON DELETE SET NULL,
                    full_name TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    job_url TEXT,
                    target_title TEXT,
                    job_description TEXT,
                    resume_data JSONB NOT NULL,
                    analysis_data JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ats_optimizations (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES auth_users(id) ON DELETE CASCADE,
                    profile_id BIGINT REFERENCES resume_profiles(id) ON DELETE SET NULL,
                    full_name TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    job_url TEXT,
                    target_title TEXT,
                    job_description TEXT,
                    original_resume_data JSONB NOT NULL,
                    optimized_resume_data JSONB NOT NULL,
                    optimization_data JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            for table_name in ("resume_drafts", "pdf_exports", "ats_analyses", "ats_optimizations"):
                cursor.execute(
                    f'ALTER TABLE "{table_name}" ADD COLUMN IF NOT EXISTS user_id BIGINT REFERENCES auth_users(id) ON DELETE CASCADE;'
                )
                cursor.execute(
                    f'ALTER TABLE "{table_name}" ADD COLUMN IF NOT EXISTS profile_id BIGINT REFERENCES resume_profiles(id) ON DELETE SET NULL;'
                )
                cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{table_name}_user_created ON "{table_name}" (user_id, created_at DESC);')
                cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{table_name}_profile_created ON "{table_name}" (profile_id, created_at DESC);')


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _public_user(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "email": row["email"],
        "created_at": _iso_or_none(row.get("created_at")),
    }


def _consume_otp(email: str, purpose: str, code: str) -> dict[str, Any]:
    normalized_email = _normalize_email(email)
    normalized_code = "".join(character for character in code.strip() if character.isdigit())
    if len(normalized_code) != 6:
        raise ValueError("Enter the 6-digit verification code.")

    _, dict_row, _ = _import_psycopg()
    with _connect(row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, code_hash, password_hash, attempts, expires_at <= NOW() AS is_expired
                FROM auth_otps
                WHERE email = %s AND purpose = %s AND consumed_at IS NULL
                ORDER BY created_at DESC, id DESC
                LIMIT 1;
                """,
                (normalized_email, purpose),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("Verification code was not found. Request a new code.")

            if row["is_expired"]:
                cursor.execute("UPDATE auth_otps SET consumed_at = NOW() WHERE id = %s;", (row["id"],))
                raise ValueError("Verification code has expired. Request a new code.")

            if int(row["attempts"]) >= OTP_MAX_ATTEMPTS:
                cursor.execute("UPDATE auth_otps SET consumed_at = NOW() WHERE id = %s;", (row["id"],))
                raise ValueError("Too many verification attempts. Request a new code.")

            if not hmac.compare_digest(row["code_hash"], _hash_otp(normalized_email, purpose, normalized_code)):
                next_attempts = int(row["attempts"]) + 1
                if next_attempts >= OTP_MAX_ATTEMPTS:
                    cursor.execute("UPDATE auth_otps SET attempts = %s, consumed_at = NOW() WHERE id = %s;", (next_attempts, row["id"]))
                    raise ValueError("Too many verification attempts. Request a new code.")
                cursor.execute("UPDATE auth_otps SET attempts = %s WHERE id = %s;", (next_attempts, row["id"]))
                raise ValueError("Invalid verification code.")

            cursor.execute("UPDATE auth_otps SET consumed_at = NOW() WHERE id = %s;", (row["id"],))

    return dict(row)


def _replace_pending_otp(
    cursor: Any,
    *,
    email: str,
    purpose: str,
    code: str,
    password_hash: str | None = None,
) -> None:
    cursor.execute(
        """
        UPDATE auth_otps
        SET consumed_at = NOW()
        WHERE email = %s AND purpose = %s AND consumed_at IS NULL;
        """,
        (email, purpose),
    )
    cursor.execute(
        """
        INSERT INTO auth_otps (email, purpose, code_hash, password_hash, expires_at)
        VALUES (%s, %s, %s, %s, %s);
        """,
        (email, purpose, _hash_otp(email, purpose, code), password_hash, _otp_expires_at()),
    )


def create_signup_otp(email: str, password: str) -> tuple[str, str]:
    normalized_email = _normalize_email(email)
    code = _generate_otp()
    _, dict_row, _ = _import_psycopg()

    with _connect(row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM auth_users WHERE email = %s;", (normalized_email,))
            if cursor.fetchone():
                raise ValueError("An account already exists for this email.")

            _replace_pending_otp(
                cursor,
                email=normalized_email,
                purpose=OTP_PURPOSE_SIGNUP,
                code=code,
                password_hash=_hash_password(password),
            )

    return normalized_email, code


def verify_signup_otp(email: str, code: str) -> dict[str, Any]:
    normalized_email = _normalize_email(email)
    row = _consume_otp(normalized_email, OTP_PURPOSE_SIGNUP, code)
    password_hash = row.get("password_hash")
    if not password_hash:
        raise ValueError("Verification code was not found. Request a new code.")

    _, dict_row, _ = _import_psycopg()
    with _connect(row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM auth_users WHERE email = %s;", (normalized_email,))
            if cursor.fetchone():
                raise ValueError("An account already exists for this email.")

            cursor.execute(
                """
                INSERT INTO auth_users (email, password_hash)
                VALUES (%s, %s)
                RETURNING id, email, created_at;
                """,
                (normalized_email, password_hash),
            )
            user_row = cursor.fetchone()

    return _public_user(user_row)


def create_password_reset_otp(email: str) -> tuple[str, str, bool]:
    normalized_email = _normalize_email(email)
    code = _generate_otp()
    _, dict_row, _ = _import_psycopg()

    with _connect(row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM auth_users WHERE email = %s;", (normalized_email,))
            user_exists = cursor.fetchone() is not None
            if user_exists:
                _replace_pending_otp(
                    cursor,
                    email=normalized_email,
                    purpose=OTP_PURPOSE_PASSWORD_RESET,
                    code=code,
                )

    return normalized_email, code, user_exists


def reset_password_with_otp(email: str, code: str, password: str) -> bool:
    normalized_email = _normalize_email(email)
    _consume_otp(normalized_email, OTP_PURPOSE_PASSWORD_RESET, code)

    with _connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE auth_users
                SET password_hash = %s
                WHERE email = %s;
                """,
                (_hash_password(password), normalized_email),
            )
            updated = bool(cursor.rowcount)
            cursor.execute(
                """
                DELETE FROM auth_sessions
                USING auth_users
                WHERE auth_sessions.user_id = auth_users.id AND auth_users.email = %s;
                """,
                (normalized_email,),
            )

    return updated


def create_user(email: str, password: str) -> dict[str, Any]:
    normalized_email = _normalize_email(email)
    _, dict_row, _ = _import_psycopg()

    with _connect(row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM auth_users WHERE email = %s;", (normalized_email,))
            if cursor.fetchone():
                raise ValueError("An account already exists for this email.")

            cursor.execute(
                """
                INSERT INTO auth_users (email, password_hash)
                VALUES (%s, %s)
                RETURNING id, email, created_at;
                """,
                (normalized_email, _hash_password(password)),
            )
            row = cursor.fetchone()

    return _public_user(row)


def authenticate_user(email: str, password: str) -> dict[str, Any] | None:
    normalized_email = _normalize_email(email)
    _, dict_row, _ = _import_psycopg()

    with _connect(row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, email, password_hash, created_at
                FROM auth_users
                WHERE email = %s;
                """,
                (normalized_email,),
            )
            row = cursor.fetchone()

    if not row or not _verify_password(password, row["password_hash"]):
        return None

    return _public_user(row)


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(40)
    token_hash = _hash_token(token)

    with _connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO auth_sessions (user_id, token_hash)
                VALUES (%s, %s);
                """,
                (user_id, token_hash),
            )

    return token


def get_user_by_session_token(token: str) -> dict[str, Any] | None:
    _, dict_row, _ = _import_psycopg()
    with _connect(row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT auth_users.id, auth_users.email, auth_users.created_at
                FROM auth_sessions
                JOIN auth_users ON auth_users.id = auth_sessions.user_id
                WHERE auth_sessions.token_hash = %s;
                """,
                (_hash_token(token),),
            )
            row = cursor.fetchone()

    return _public_user(row) if row else None


def delete_session(token: str) -> bool:
    with _connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM auth_sessions WHERE token_hash = %s;", (_hash_token(token),))
            return bool(cursor.rowcount)


def _ensure_default_profile(user_id: int) -> dict[str, Any]:
    _, dict_row, _ = _import_psycopg()
    with _connect(row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, created_at, updated_at
                FROM resume_profiles
                WHERE user_id = %s
                ORDER BY created_at ASC, id ASC
                LIMIT 1;
                """,
                (user_id,),
            )
            row = cursor.fetchone()

            if not row:
                cursor.execute(
                    """
                    INSERT INTO resume_profiles (user_id, name)
                    VALUES (%s, %s)
                    RETURNING id, name, created_at, updated_at;
                    """,
                    (user_id, "Default Profile"),
                )
                row = cursor.fetchone()

            cursor.execute("UPDATE resume_drafts SET profile_id = %s WHERE user_id = %s AND profile_id IS NULL;", (row["id"], user_id))
            cursor.execute("UPDATE pdf_exports SET profile_id = %s WHERE user_id = %s AND profile_id IS NULL;", (row["id"], user_id))
            cursor.execute("UPDATE ats_analyses SET profile_id = %s WHERE user_id = %s AND profile_id IS NULL;", (row["id"], user_id))
            cursor.execute("UPDATE ats_optimizations SET profile_id = %s WHERE user_id = %s AND profile_id IS NULL;", (row["id"], user_id))

    return _profile_payload({**row, "latest_saved_at": None, "has_saved_draft": False})


def _require_profile(user_id: int, profile_id: int | None) -> dict[str, Any]:
    if profile_id is None:
        return _ensure_default_profile(user_id)

    _, dict_row, _ = _import_psycopg()
    with _connect(row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, created_at, updated_at
                FROM resume_profiles
                WHERE user_id = %s AND id = %s;
                """,
                (user_id, profile_id),
            )
            row = cursor.fetchone()

    if not row:
        raise ValueError("Resume profile was not found.")

    return _profile_payload({**row, "latest_saved_at": None, "has_saved_draft": False})


def create_resume_profile(user_id: int, name: str) -> dict[str, Any]:
    normalized_name = " ".join(name.strip().split())
    if not normalized_name:
        raise ValueError("Profile name is required.")

    _, dict_row, _ = _import_psycopg()
    with _connect(row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM resume_profiles
                WHERE user_id = %s AND lower(name) = lower(%s);
                """,
                (user_id, normalized_name),
            )
            if cursor.fetchone():
                raise ValueError("A profile with this name already exists.")

            cursor.execute(
                """
                INSERT INTO resume_profiles (user_id, name)
                VALUES (%s, %s)
                RETURNING id, name, created_at, updated_at;
                """,
                (user_id, normalized_name),
            )
            row = cursor.fetchone()

    return _profile_payload({**row, "latest_saved_at": None, "has_saved_draft": False})


def list_resume_profiles(user_id: int) -> list[dict[str, Any]]:
    _ensure_default_profile(user_id)
    _, dict_row, _ = _import_psycopg()
    with _connect(row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    profile.id,
                    profile.name,
                    profile.created_at,
                    profile.updated_at,
                    latest.created_at AS latest_saved_at,
                    latest.id IS NOT NULL AS has_saved_draft
                FROM resume_profiles AS profile
                LEFT JOIN LATERAL (
                    SELECT id, created_at
                    FROM resume_drafts
                    WHERE user_id = %s AND profile_id = profile.id
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                ) AS latest ON TRUE
                WHERE profile.user_id = %s
                ORDER BY profile.updated_at DESC, profile.id DESC;
                """,
                (user_id, user_id),
            )
            rows = cursor.fetchall()

    return [_profile_payload(row) for row in rows]


def save_resume_draft(
    resume: Any,
    template_id: str,
    section_color: str | None,
    user_id: int,
    profile_id: int | None = None,
) -> dict[str, Any]:
    profile = _require_profile(user_id, profile_id)
    resume_data = _json_ready(resume)
    full_name, email = _resume_identity(resume_data)
    _, dict_row, _ = _import_psycopg()

    with _connect(row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO resume_drafts (user_id, profile_id, full_name, email, template_id, section_color, resume_data)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at;
                """,
                (user_id, profile["id"], full_name, email, template_id, section_color, _as_jsonb(resume_data)),
            )
            row = cursor.fetchone()
            cursor.execute(
                "UPDATE resume_profiles SET updated_at = NOW() WHERE user_id = %s AND id = %s;",
                (user_id, profile["id"]),
            )

    return {"id": row["id"], "profile_id": profile["id"], "saved_at": _iso_or_none(row["created_at"])}


def get_latest_resume_draft(user_id: int, profile_id: int | None = None) -> dict[str, Any] | None:
    profile = _require_profile(user_id, profile_id)
    _, dict_row, _ = _import_psycopg()
    with _connect(row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, profile_id, template_id, section_color, resume_data, created_at
                FROM resume_drafts
                WHERE user_id = %s AND profile_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT 1;
                """,
                (user_id, profile["id"]),
            )
            row = cursor.fetchone()

    if not row:
        return None

    return {
        "id": row["id"],
        "profile_id": row["profile_id"],
        "template_id": row["template_id"],
        "section_color": row["section_color"],
        "resume": row["resume_data"],
        "saved_at": _iso_or_none(row["created_at"]),
    }


def clear_resume_drafts(user_id: int, profile_id: int | None = None) -> int:
    profile = _require_profile(user_id, profile_id)
    with _connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM resume_drafts WHERE user_id = %s AND profile_id = %s;", (user_id, profile["id"]))
            return cursor.rowcount or 0


def save_pdf_export(
    *,
    resume: Any,
    template_id: str,
    section_color: str | None,
    filename: str,
    pdf_bytes: bytes,
    user_id: int,
    profile_id: int | None = None,
) -> dict[str, Any]:
    profile = _require_profile(user_id, profile_id)
    resume_data = _json_ready(resume)
    full_name, email = _resume_identity(resume_data)
    _, dict_row, _ = _import_psycopg()

    with _connect(row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO pdf_exports (
                    user_id, profile_id, full_name, email, template_id, section_color, filename, resume_data, pdf_bytes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at;
                """,
                (user_id, profile["id"], full_name, email, template_id, section_color, filename, _as_jsonb(resume_data), pdf_bytes),
            )
            row = cursor.fetchone()

    return {"id": row["id"], "saved_at": _iso_or_none(row["created_at"])}


def save_ats_analysis(
    *,
    resume: Any,
    analysis: Any,
    job_url: str | None,
    target_title: str | None,
    job_description: str | None,
    user_id: int,
    profile_id: int | None = None,
) -> dict[str, Any]:
    profile = _require_profile(user_id, profile_id)
    resume_data = _json_ready(resume)
    analysis_data = _json_ready(analysis)
    full_name, email = _resume_identity(resume_data)
    _, dict_row, _ = _import_psycopg()

    with _connect(row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ats_analyses (
                    user_id, profile_id, full_name, email, job_url, target_title, job_description, resume_data, analysis_data
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at;
                """,
                (
                    user_id,
                    profile["id"],
                    full_name,
                    email,
                    job_url,
                    target_title,
                    job_description,
                    _as_jsonb(resume_data),
                    _as_jsonb(analysis_data),
                ),
            )
            row = cursor.fetchone()

    return {"id": row["id"], "saved_at": _iso_or_none(row["created_at"])}


def save_ats_optimization(
    *,
    original_resume: Any,
    optimized_resume: Any,
    optimization: Any,
    job_url: str | None,
    target_title: str | None,
    job_description: str | None,
    user_id: int,
    profile_id: int | None = None,
) -> dict[str, Any]:
    profile = _require_profile(user_id, profile_id)
    original_resume_data = _json_ready(original_resume)
    optimized_resume_data = _json_ready(optimized_resume)
    optimization_data = _json_ready(optimization)
    full_name, email = _resume_identity(optimized_resume_data)
    _, dict_row, _ = _import_psycopg()

    with _connect(row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ats_optimizations (
                    user_id, profile_id, full_name, email, job_url, target_title, job_description,
                    original_resume_data, optimized_resume_data, optimization_data
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at;
                """,
                (
                    user_id,
                    profile["id"],
                    full_name,
                    email,
                    job_url,
                    target_title,
                    job_description,
                    _as_jsonb(original_resume_data),
                    _as_jsonb(optimized_resume_data),
                    _as_jsonb(optimization_data),
                ),
            )
            row = cursor.fetchone()

    return {"id": row["id"], "saved_at": _iso_or_none(row["created_at"])}
