from sqlalchemy.orm import Session
from fastapi import HTTPException, Depends, Request
from app.models import User
from app.database import SessionLocal
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def authenticate_user(db, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None

    if not pwd_context.verify(password, user.password):
        return None
    return user



def get_current_user(db: Session = Depends(get_db), request: Request = None):
    session = request.session

    user_id = session.get("user_id")
    if not user_id:
        return None

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
