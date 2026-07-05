import uuid
from datetime import datetime

from app.schemas.common import ORMModel


class AuditLogResponse(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    organization_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: uuid.UUID | None
    before_state: dict | None
    after_state: dict | None
    ip_address: str | None
    created_at: datetime
