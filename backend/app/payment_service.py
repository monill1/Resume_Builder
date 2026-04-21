from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class PaymentConfigurationError(RuntimeError):
    pass


class PaymentGatewayError(RuntimeError):
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


def _razorpay_keys() -> tuple[str, str]:
    _load_local_env()
    key_id = os.getenv("RAZORPAY_KEY_ID", "").strip()
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
    if not key_id or not key_secret:
        raise PaymentConfigurationError("RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET must be configured.")
    return key_id, key_secret


def get_razorpay_key_id() -> str:
    key_id, _ = _razorpay_keys()
    return key_id


def create_razorpay_order(
    *,
    amount_paise: int,
    currency: str,
    receipt: str,
    notes: dict[str, str],
) -> dict[str, Any]:
    key_id, key_secret = _razorpay_keys()
    payload = {
        "amount": amount_paise,
        "currency": currency,
        "receipt": receipt,
        "notes": notes,
    }
    credentials = base64.b64encode(f"{key_id}:{key_secret}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        "https://api.razorpay.com/v1/orders",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise PaymentGatewayError(detail or "Razorpay order creation failed.") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise PaymentGatewayError("Razorpay order creation failed.") from exc


def verify_razorpay_signature(
    *,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> bool:
    _, key_secret = _razorpay_keys()
    message = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
    expected_signature = hmac.new(key_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_signature, razorpay_signature)
