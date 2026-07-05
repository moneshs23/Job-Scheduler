import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import (
    create_access_token,
    create_refresh_token,
    generate_api_key,
    hash_password,
    verify_password,
)
from app.models.api_key import APIKey
from app.models.organization import Organization, OrganizationMember, User
from app.repositories.api_key import APIKeyRepository
from app.repositories.organization import OrganizationRepository, UserRepository
from app.schemas.auth import APIKeyCreateRequest, RegisterRequest


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or uuid.uuid4().hex[:8]


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.users = UserRepository(db)
        self.orgs = OrganizationRepository(db)
        self.api_keys = APIKeyRepository(db)

    async def register(self, payload: RegisterRequest) -> User:
        if await self.users.get_by_email(payload.email):
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

        user = await self.users.add(
            User(
                email=payload.email,
                password_hash=hash_password(payload.password),
                full_name=payload.full_name,
                role="admin",
            )
        )

        base_slug = slugify(payload.organization_name)
        slug = base_slug
        suffix = 1
        while await self.orgs.get_by_slug(slug):
            suffix += 1
            slug = f"{base_slug}-{suffix}"

        org = await self.orgs.add(Organization(name=payload.organization_name, slug=slug))
        self.db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.users.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is deactivated")
        return user

    @staticmethod
    def issue_tokens(user: User) -> tuple[str, str]:
        return create_access_token(user.id), create_refresh_token(user.id)

    async def create_api_key(self, user: User, payload: APIKeyCreateRequest) -> tuple[APIKey, str]:
        full_key, prefix, key_hash = generate_api_key()
        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)
            if payload.expires_in_days
            else None
        )
        api_key = await self.api_keys.add(
            APIKey(
                user_id=user.id,
                project_id=payload.project_id,
                key_hash=key_hash,
                key_prefix=prefix,
                name=payload.name,
                scopes=payload.scopes,
                expires_at=expires_at,
            )
        )
        await self.db.commit()
        return api_key, full_key

    async def revoke_api_key(self, user: User, api_key_id: uuid.UUID) -> APIKey:
        api_key = await self.api_keys.get(api_key_id)
        if api_key is None or api_key.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
        if api_key.revoked_at is None:
            api_key.revoked_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(api_key)
        return api_key
