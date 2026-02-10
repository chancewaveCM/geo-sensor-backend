import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"


def validate_password_strength(password: str) -> str:
    """Validate password meets complexity requirements."""
    if not any(c.isupper() for c in password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one digit")
    if not any(c in SPECIAL_CHARS for c in password):
        raise ValueError("Password must contain at least one special character")
    return password


class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_password_strength(v)


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    avatar_url: str | None = None
    notification_preferences: dict | None = None
    created_at: datetime

    @field_validator("notification_preferences", mode="before")
    @classmethod
    def parse_notification_preferences(cls, v: str | dict | None) -> dict | None:
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        try:
            return json.loads(v)
        except (json.JSONDecodeError, TypeError):
            return None


class UserProfileUpdate(BaseModel):
    full_name: str | None = Field(None, max_length=255)
    avatar_url: str | None = None
    notification_preferences: str | None = Field(default=None, max_length=4096)

    @field_validator("notification_preferences")
    @classmethod
    def validate_notification_json(cls, v: str | None) -> str | None:
        if v is None:
            return None
        try:
            parsed = json.loads(v)
            if not isinstance(parsed, dict):
                raise ValueError("Must be a JSON object")
        except (json.JSONDecodeError, TypeError) as e:
            raise ValueError("Invalid JSON string") from e
        return v


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)


class AvatarUploadRequest(BaseModel):
    avatar_data: str = Field(..., description="Base64 encoded image data")
    content_type: str = Field(default="image/png", pattern=r"^image/(png|jpeg|gif|webp)$")
