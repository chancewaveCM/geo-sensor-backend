"""User management endpoints."""

from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/check-email", status_code=status.HTTP_200_OK)
async def check_email_availability(
    email: str,
    db: DbSession,
) -> dict:
    """Check if email is available for registration."""
    existing_user = await user_service.get_user_by_email(db, email)
    is_available = existing_user is None
    return {
        "available": is_available,
        "message": "사용 가능한 이메일입니다" if is_available else "이미 등록된 이메일입니다",
    }
