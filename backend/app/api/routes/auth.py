from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import create_access_token
from app.schemas.user import UserCreate, UserRead, Token, UserLogin
from app.models.audit_log import AuditEventType
from app.services.audit_service import create_audit_log
from app.services.user_service import (
    authenticate_user,
    create_user,
    get_user_by_email,
    get_user_by_username,
)

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    existing_user_by_email = get_user_by_email(db, user_in.email)
    if existing_user_by_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    existing_user_by_username = get_user_by_username(db, user_in.username)
    if existing_user_by_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )
        
    user = create_user(db, user_in)
    
    create_audit_log(
        db=db,
        event_type=AuditEventType.USER_REGISTERED,
        user=user,
        message=f"User registered: {user.email}",
    )
    return user

@router.post("/login", response_model=Token)
def login_user(user_in: UserLogin, db: Session = Depends(get_db)) -> Token:
    user = authenticate_user(db, user_in.email, user_in.password)
    if not user:
        create_audit_log(
            db=db,
            event_type=AuditEventType.LOGIN_FAILED,
            email=user_in.email,
            message=f"Failed login attempt for email: {user_in.email}",
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    create_audit_log(
        db=db,
        event_type=AuditEventType.LOGIN_SUCCESS,
        user=user,
        message=f"Successful login for user: {user.email}",
    )
    
    access_token = create_access_token(user.email)
    
    return Token(
        access_token=access_token,
        token_type="bearer")