import uuid
from dataclasses import dataclass, field

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import TokenType, decode_token, hash_api_key
from app.database.session import get_db
from app.models.api_key import APIKey
from app.models.organization import OrganizationMember, Project, User

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    user: User
    project_ids: set[uuid.UUID] = field(default_factory=set)
    scopes: set[str] = field(default_factory=set)
    is_api_key: bool = False

    def can_access_project(self, project_id: uuid.UUID) -> bool:
        return not self.is_api_key or project_id in self.project_ids


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")

    try:
        user_id = decode_token(credentials.credentials, TokenType.ACCESS)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Principal:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing credentials")

    token = credentials.credentials
    if token.startswith("djs_"):
        key_hash = hash_api_key(token)
        result = await db.execute(select(APIKey).where(APIKey.key_hash == key_hash))
        api_key = result.scalar_one_or_none()
        if api_key is None or api_key.revoked_at is not None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
        user = await db.get(User, api_key.user_id)
        if user is None or not user.is_active:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
        project_ids = {api_key.project_id} if api_key.project_id else set()
        return Principal(
            user=user,
            project_ids=project_ids,
            scopes=set(api_key.scopes or []),
            is_api_key=True,
        )

    user = await get_current_user(credentials, db)
    return Principal(user=user)


async def require_project_access(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    if principal.is_api_key:
        if not principal.can_access_project(project_id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "API key not scoped to this project")
        return project

    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == project.organization_id,
            OrganizationMember.user_id == principal.user.id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this organization")
    return project


def require_org_role(*allowed_roles: str):
    async def checker(
        organization_id: uuid.UUID,
        principal: Principal = Depends(get_current_principal),
        db: AsyncSession = Depends(get_db),
    ) -> OrganizationMember:
        result = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == principal.user.id,
            )
        )
        member = result.scalar_one_or_none()
        if member is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this organization")
        if allowed_roles and member.role not in allowed_roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role for this action")
        return member

    return checker
