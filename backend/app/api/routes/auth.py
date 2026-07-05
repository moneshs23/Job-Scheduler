import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.security import TokenType, decode_token
from app.database.session import get_db
from app.models.organization import User
from app.repositories.api_key import APIKeyRepository
from app.repositories.organization import UserRepository
from app.schemas.auth import (
    APIKeyCreatedResponse,
    APIKeyCreateRequest,
    APIKeyResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    service = AuthService(db)
    user = await service.register(payload)
    access, refresh = service.issue_tokens(user)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    service = AuthService(db)
    user = await service.authenticate(payload.email, payload.password)
    access, refresh = service.issue_tokens(user)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    try:
        user_id = decode_token(payload.refresh_token, TokenType.REFRESH)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    user = await UserRepository(db).get(user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")

    access, new_refresh = AuthService.issue_tokens(user)
    return TokenResponse(access_token=access, refresh_token=new_refresh)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/api-keys", response_model=APIKeyCreatedResponse, status_code=201)
async def create_api_key(
    payload: APIKeyCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIKeyCreatedResponse:
    service = AuthService(db)
    api_key, full_key = await service.create_api_key(current_user, payload)
    return APIKeyCreatedResponse(
        id=api_key.id, name=api_key.name, key=full_key, key_prefix=api_key.key_prefix, scopes=api_key.scopes or []
    )


@router.get("/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list:
    return await APIKeyRepository(db).list_for_user(current_user.id)


@router.delete("/api-keys/{api_key_id}", response_model=APIKeyResponse)
async def revoke_api_key(
    api_key_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    return await service.revoke_api_key(current_user, api_key_id)
