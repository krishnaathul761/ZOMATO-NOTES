from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# User schemas
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    name:     str
    email:    EmailStr
    password: str = Field(min_length=8)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name must not be empty or whitespace")
        return v.strip()


class UserResponse(BaseModel):
    id:         int
    name:       str
    email:      str
    created_at: datetime
    # password is intentionally excluded

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Note schemas
# ---------------------------------------------------------------------------

class NoteCreate(BaseModel):
    title:    str     = Field(min_length=1, max_length=120)
    content:  str     = Field(min_length=1)
    tag:      Optional[str] = None
    severity: Optional[str] = None   # "P0", "P1", "P2", "P3"
    owner_id: int


class NoteUpdate(BaseModel):
    title:    Optional[str] = Field(default=None, min_length=1, max_length=120)
    content:  Optional[str] = Field(default=None, min_length=1)
    tag:      Optional[str] = None
    severity: Optional[str] = None


class NoteResponse(BaseModel):
    id:            int
    title:         str
    content:       str
    tag:           Optional[str]
    severity:      Optional[str] = None
    owner_id:      int
    created_at:    datetime
    ai_suggestion: Any = None   # populated by Phase 4; None for all existing notes

    model_config = ConfigDict(from_attributes=True)
