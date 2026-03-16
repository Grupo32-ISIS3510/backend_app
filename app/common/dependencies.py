from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import service as auth_service
from app.common.exceptions import AppException, ErrorCode

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    token_data = auth_service.decode_access_token(token)
    user = auth_service.get_user_by_id(db, str(token_data.user_id))
    if not user or not bool(user.is_active):
        raise AppException(
            status_code=401,
            code=ErrorCode.UNAUTHORIZED,
            message="Usuario no encontrado o inactivo.",
        )
    return user
