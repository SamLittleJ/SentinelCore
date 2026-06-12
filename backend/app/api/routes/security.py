from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.security_event import SecurityEvent
from app.models.user import User, UserRole
from app.schemas.security_event import SecurityEventRead
from app.services.security_event_service import list_security_events

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/events", response_model=list[SecurityEventRead])
def read_security_events(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(
            require_role(UserRole.ADMIN, UserRole.OWNER, UserRole.SECURITY_ANALYST)
        ),
    ],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[SecurityEvent]:
    return list_security_events(db, limit=limit)
