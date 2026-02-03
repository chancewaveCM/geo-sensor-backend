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
    password: str | None = Field(None, min_length=8, max_length=128)

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
    created_at: datetime
