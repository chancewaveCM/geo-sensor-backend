"""Base schema classes for shared functionality."""

from pydantic import BaseModel, ConfigDict


class BaseResponseSchema(BaseModel):
    """Base class for all response schemas with ORM mode enabled."""

    model_config = ConfigDict(from_attributes=True)
