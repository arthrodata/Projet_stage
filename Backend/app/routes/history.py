from __future__ import annotations

from fastapi import APIRouter, Depends

from Backend.app.utils.auth import require_current_user
from Backend.app.utils.history import list_search_history


router = APIRouter(prefix="/history", tags=["history"])


@router.get("")
def history(limit: int = 10, user: dict = Depends(require_current_user)):
    return list_search_history(user, limit=limit)
