from __future__ import annotations

import json
import os
import hashlib
import hmac
import secrets
from datetime import datetime
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


def _iso_or_none(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None


PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 310_000


def _hash_password(password: str) -> str:
    salt = secrets.token_urlsafe(24)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"{PASSWORD_HASH_ALGORITHM}${PASSWORD_HASH_ITERATIONS}${salt}${password_hash}"


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
                CREATE TABLE IF NOT EXISTS resume_drafts (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES auth_users(id) ON DELETE CASCADE,
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
                cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{table_name}_user_created ON "{table_name}" (user_id, created_at DESC);')


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _public_user(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "email": row["email"],
        "created_at": _iso_or_none(row.get("created_at")),
    }


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


def save_resume_draft(resume: Any, template_id: str, section_color: str | None, user_id: int) -> dict[str, Any]:
    resume_data = _json_ready(resume)
    full_name, email = _resume_identity(resume_data)
    _, dict_row, _ = _import_psycopg()

    with _connect(row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO resume_drafts (user_id, full_name, email, template_id, section_color, resume_data)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, created_at;
                """,
                (user_id, full_name, email, template_id, section_color, _as_jsonb(resume_data)),
            )
            row = cursor.fetchone()

    return {"id": row["id"], "saved_at": _iso_or_none(row["created_at"])}


def get_latest_resume_draft(user_id: int) -> dict[str, Any] | None:
    _, dict_row, _ = _import_psycopg()
    with _connect(row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, template_id, section_color, resume_data, created_at
                FROM resume_drafts
                WHERE user_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT 1;
                """,
                (user_id,),
            )
            row = cursor.fetchone()

    if not row:
        return None

    return {
        "id": row["id"],
        "template_id": row["template_id"],
        "section_color": row["section_color"],
        "resume": row["resume_data"],
        "saved_at": _iso_or_none(row["created_at"]),
    }


def clear_resume_drafts(user_id: int) -> int:
    with _connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM resume_drafts WHERE user_id = %s;", (user_id,))
            return cursor.rowcount or 0


def save_pdf_export(
    *,
    resume: Any,
    template_id: str,
    section_color: str | None,
    filename: str,
    pdf_bytes: bytes,
    user_id: int,
) -> dict[str, Any]:
    resume_data = _json_ready(resume)
    full_name, email = _resume_identity(resume_data)
    _, dict_row, _ = _import_psycopg()

    with _connect(row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO pdf_exports (
                    user_id, full_name, email, template_id, section_color, filename, resume_data, pdf_bytes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at;
                """,
                (user_id, full_name, email, template_id, section_color, filename, _as_jsonb(resume_data), pdf_bytes),
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
) -> dict[str, Any]:
    resume_data = _json_ready(resume)
    analysis_data = _json_ready(analysis)
    full_name, email = _resume_identity(resume_data)
    _, dict_row, _ = _import_psycopg()

    with _connect(row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ats_analyses (
                    user_id, full_name, email, job_url, target_title, job_description, resume_data, analysis_data
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at;
                """,
                (
                    user_id,
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
) -> dict[str, Any]:
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
                    user_id, full_name, email, job_url, target_title, job_description,
                    original_resume_data, optimized_resume_data, optimization_data
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at;
                """,
                (
                    user_id,
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
