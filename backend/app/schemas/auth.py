import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    organization_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(ORMModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool


class APIKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    project_id: uuid.UUID | None = None
    scopes: list[str] = Field(default_factory=list)
    expires_in_days: int | None = None


class APIKeyCreatedResponse(ORMModel):
    id: uuid.UUID
    name: str
    key: str
    key_prefix: str
    scopes: list[str]


class APIKeyResponse(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID | None
    name: str
    key_prefix: str
    scopes: list[str] | None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime
