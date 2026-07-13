from __future__ import annotations

import secrets
import string
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from Backend.app.utils.auth import hash_password, require_admin_user
from Backend.app.utils.database import iter_connection


router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_USER_COLUMNS = """
    id, email, first_name, last_name, is_validated, is_admin,
    validated_at, validated_by, last_login_at, last_activity_at, created_at
"""


def _public_admin_user(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "email": row["email"],
        "first_name": row.get("first_name") or "",
        "last_name": row.get("last_name") or "",
        "display_name": " ".join(
            part for part in [row.get("first_name") or "", row.get("last_name") or ""] if part
        ).strip(),
        "is_validated": bool(row.get("is_validated")),
        "is_admin": bool(row.get("is_admin")),
        "validated_at": row.get("validated_at"),
        "validated_by": row.get("validated_by"),
        "last_login_at": row.get("last_login_at"),
        "last_activity_at": row.get("last_activity_at"),
        "created_at": row["created_at"],
    }


def _get_admin_user(user_id: int) -> dict[str, Any] | None:
    with iter_connection() as conn:
        row = conn.execute(
            f"SELECT {ADMIN_USER_COLUMNS} FROM users WHERE id = ?",
            (int(user_id),),
        ).fetchone()
    return dict(row) if row else None


def _generate_temporary_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@router.get("/users")
def list_users(admin: dict = Depends(require_admin_user)):
    with iter_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT {ADMIN_USER_COLUMNS}
            FROM users
            ORDER BY is_admin DESC, is_validated ASC, created_at DESC
            """
        ).fetchall()
    return {"users": [_public_admin_user(dict(row)) for row in rows]}


@router.delete("/history")
def clear_search_history(admin: dict = Depends(require_admin_user)):
    with iter_connection() as conn:
        cur = conn.execute("DELETE FROM search_history")
    return {"deleted": int(cur.rowcount if cur.rowcount is not None else 0)}


@router.delete("/users/unvalidated")
def delete_unvalidated_users(admin: dict = Depends(require_admin_user)):
    with iter_connection() as conn:
        cur = conn.execute(
            """
            DELETE FROM users
            WHERE is_validated = 0
              AND is_admin = 0
              AND id != ?
            """,
            (int(admin["id"]),),
        )
    return {"deleted": int(cur.rowcount if cur.rowcount is not None else 0)}


@router.patch("/users/{user_id}/validate")
def validate_user(user_id: int, admin: dict = Depends(require_admin_user)):
    with iter_connection() as conn:
        cur = conn.execute(
            """
            UPDATE users
            SET is_validated = 1,
                validated_at = CURRENT_TIMESTAMP,
                validated_by = ?
            WHERE id = ?
            """,
            (int(admin["id"]), int(user_id)),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    user = _get_admin_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    return {"user": _public_admin_user(user)}


@router.patch("/users/{user_id}/password")
def reset_user_password(user_id: int, admin: dict = Depends(require_admin_user)):
    if int(user_id) == int(admin["id"]):
        raise HTTPException(status_code=400, detail="Impossible de regenerer votre propre mot de passe.")

    temporary_password = _generate_temporary_password()
    with iter_connection() as conn:
        row = conn.execute(
            "SELECT id, is_admin FROM users WHERE id = ?",
            (int(user_id),),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
        if int(row["is_admin"] or 0):
            raise HTTPException(status_code=400, detail="Impossible de regenerer le mot de passe d'un administrateur.")
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(temporary_password), int(user_id)),
        )

    user = _get_admin_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    return {
        "user": _public_admin_user(user),
        "temporary_password": temporary_password,
        "message": "Mot de passe temporaire regenere. Il est affiche une seule fois.",
    }


@router.patch("/users/{user_id}/invalidate")
def invalidate_user(user_id: int, admin: dict = Depends(require_admin_user)):
    if int(user_id) == int(admin["id"]):
        raise HTTPException(status_code=400, detail="Impossible d'invalider votre propre compte administrateur.")
    with iter_connection() as conn:
        cur = conn.execute(
            """
            UPDATE users
            SET is_validated = 0,
                validated_at = NULL,
                validated_by = NULL
            WHERE id = ?
            """,
            (int(user_id),),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    user = _get_admin_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    return {"user": _public_admin_user(user)}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: dict = Depends(require_admin_user)):
    if int(user_id) == int(admin["id"]):
        raise HTTPException(status_code=400, detail="Impossible de supprimer votre propre compte administrateur.")
    with iter_connection() as conn:
        row = conn.execute(
            "SELECT id, is_admin FROM users WHERE id = ?",
            (int(user_id),),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
        if int(row["is_admin"] or 0):
            raise HTTPException(status_code=400, detail="Impossible de supprimer un autre administrateur.")
        conn.execute("DELETE FROM users WHERE id = ?", (int(user_id),))
    return {"deleted": True, "user_id": int(user_id)}
