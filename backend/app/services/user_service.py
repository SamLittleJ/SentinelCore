from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate

def get_user_by_email(db: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    return db.scalar(statement)

def get_user_by_username(db: Session, username: str) -> User | None:
    statement = select(User).where(User.username == username)
    return db.scalar(statement)

def create_user(db: Session, user_in: UserCreate) -> User:
    user = User(
        username = user_in.username,
        email = user_in.email,
        hashed_password = hash_password(user_in.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user