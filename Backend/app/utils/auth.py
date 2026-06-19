from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

from fastapi import Depends, Header, HTTPException

from Backend.app.utils.database import iter_connection


TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7


def _secret_key() -> bytes:
    configured = os.getenv("APP_SECRET_KEY", "").strip()
    if configured:
        return configured.encode("utf-8")
    return b"dev-secret-change-me"


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"pbkdf2_sha256${_b64url_encode(salt)}${_b64url_encode(digest)}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, salt_b64, digest_b64 = stored_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    salt = _b64url_decode(salt_b64)
    expected = _b64url_decode(digest_b64)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return hmac.compare_digest(actual, expected)


def create_token(user: dict[str, Any]) -> str:
    payload = {
        "sub": int(user["id"]),
        "email": str(user["email"]),
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(_secret_key(), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return f"{payload_b64}.{_b64url_encode(signature)}"


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        payload_b64, signature_b64 = token.split(".", 1)
        expected = hmac.new(_secret_key(), payload_b64.encode("ascii"), hashlib.sha256).digest()
        actual = _b64url_decode(signature_b64)
        if not hmac.compare_digest(actual, expected):
            return None
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if int(payload.get("exp") or 0) < int(time.time()):
        return None
    return payload if isinstance(payload, dict) else None


USER_COLUMNS = "id, email, first_name, last_name, password_hash, created_at"


def get_user_by_email(email: str) -> dict[str, Any] | None:
    with iter_connection() as conn:
        row = conn.execute(
            f"SELECT {USER_COLUMNS} FROM users WHERE lower(email) = lower(?)",
            (email.strip(),),
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with iter_connection() as conn:
        row = conn.execute(
            f"SELECT {USER_COLUMNS} FROM users WHERE id = ?",
            (int(user_id),),
        ).fetchone()
    return dict(row) if row else None


def create_user(email: str, password: str, first_name: str = "", last_name: str = "") -> dict[str, Any]:
    clean_email = email.strip().lower()
    clean_first_name = " ".join(str(first_name or "").strip().split())
    clean_last_name = " ".join(str(last_name or "").strip().split())
    if not clean_email or "@" not in clean_email:
        raise HTTPException(status_code=400, detail="Email invalide.")
    if not clean_first_name or not clean_last_name:
        raise HTTPException(status_code=400, detail="Prenom et nom requis.")
    if len(password or "") < 6:
        raise HTTPException(status_code=400, detail="Mot de passe trop court.")

    try:
        with iter_connection() as conn:
            cur = conn.execute(
                "INSERT INTO users (email, first_name, last_name, password_hash) VALUES (?, ?, ?, ?)",
                (clean_email, clean_first_name, clean_last_name, hash_password(password)),
            )
            user_id = int(cur.lastrowid)
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise HTTPException(status_code=409, detail="Un compte existe deja avec cet email.")
        raise

    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=500, detail="Compte cree mais introuvable.")
    return user


def authenticate_user(email: str, password: str) -> dict[str, Any] | None:
    user = get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        return None
    return user


def optional_current_user(authorization: str | None = Header(default=None)) -> dict[str, Any] | None:
    if not authorization:
        return None
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None
    payload = decode_token(authorization[len(prefix):].strip())
    if not payload:
        return None
    return get_user_by_id(int(payload["sub"]))


def require_current_user(user: dict[str, Any] | None = Depends(optional_current_user)) -> dict[str, Any]:
    if not user:
        raise HTTPException(status_code=401, detail="Authentification requise.")
    return user
