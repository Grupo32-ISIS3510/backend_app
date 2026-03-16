from pydantic import BaseModel, EmailStr, UUID4
from datetime import datetime
from typing import Optional

# ── Entrada: datos que llegan del cliente ──────────────────

class UserRegister(BaseModel):
    email: EmailStr          # Pydantic valida que sea un email válido
    full_name: str
    password: str
    location: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

# ── Salida: datos que devuelves al cliente ─────────────────

class UserResponse(BaseModel):
    id: UUID4
    email: str
    full_name: str
    is_premium: bool
    location: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True  # permite crear este schema desde un objeto SQLAlchemy

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class TokenData(BaseModel):
    user_id: Optional[str] = None  # payload decodificado del JWT