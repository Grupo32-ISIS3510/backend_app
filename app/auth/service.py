from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.auth.models import User
from app.auth.schemas import UserRegister, TokenData
from app.config import get_settings

settings = get_settings()

# Contexto de hashing — bcrypt es el algoritmo estándar para contraseñas.
# 'deprecated="auto"' migra automáticamente hashes viejos si cambias el algoritmo.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Contraseñas ────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT ────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.jwt_expiration_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def decode_access_token(token: str) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return TokenData(user_id=str(user_id))
    except JWTError:
        raise credentials_exception


# ── Usuarios ───────────────────────────────────────────────

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()

def create_user(db: Session, data: UserRegister) -> User:
    # Verificar que el email no esté registrado
    if get_user_by_email(db, data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una cuenta con este email"
        )
    user = User(
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        location=data.location
    )
    db.add(user)
    db.commit()
    db.refresh(user)  # recarga el objeto desde la BD para obtener el id generado
    return user

def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, str(user.password_hash)):
        return None
    return user