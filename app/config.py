from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Base de datos
    database_url: str

    # JWT
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    # Entorno
    app_env: str = "development"
    app_name: str = "Second Serving Backend"
    cors_origins: str = ""

    # Notificaciones
    notifications_scheduler_hours: int = 1
    notifications_qa_endpoint_enabled: bool = True

    # Servicios externos (opcionales en desarrollo)
    firebase_credentials_path: str = ""
    google_application_credentials: str = ""
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
