from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from Backend.app.utils.auth import (
    authenticate_user,
    create_token,
    create_user,
    ensure_user_can_login,
    mark_user_login,
    require_current_user,
)


router = APIRouter(prefix="/auth", tags=["auth"])


class AuthPayload(BaseModel):
    email: str
    password: str
    first_name: str | None = None
    last_name: str | None = None


def _public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "first_name": user.get("first_name") or "",
        "last_name": user.get("last_name") or "",
        "display_name": " ".join(
            part for part in [user.get("first_name") or "", user.get("last_name") or ""] if part
        ).strip(),
        "is_validated": bool(user.get("is_validated")),
        "is_admin": bool(user.get("is_admin")),
        "last_login_at": user.get("last_login_at"),
        "last_activity_at": user.get("last_activity_at"),
        "created_at": user["created_at"],
    }


@router.post("/register")
def register(payload: AuthPayload):
    user = create_user(payload.email, payload.password, payload.first_name or "", payload.last_name or "")
    if not user.get("is_validated"):
        return {
            "status": "pending_validation",
            "message": "Account created. It must be validated by an administrator before you can sign in.",
            "user": _public_user(user),
        }
    return {"access_token": create_token(user), "token_type": "bearer", "user": _public_user(user)}


@router.post("/login")
def login(payload: AuthPayload):
    user = authenticate_user(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    ensure_user_can_login(user)
    user = mark_user_login(int(user["id"]))
    return {"access_token": create_token(user), "token_type": "bearer", "user": _public_user(user)}


@router.get("/me")
def me(user: dict = Depends(require_current_user)):
    return _public_user(user)
