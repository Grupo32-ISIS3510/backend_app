from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import get_settings

settings = get_settings()

# Motor de conexión a PostgreSQL
# pool_pre_ping=True verifica que la conexión siga viva antes de usarla.
# Esto evita errores silenciosos cuando la BD estuvo inactiva un tiempo.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True
)


# Fábrica de sesiones — cada llamada a SessionLocal() abre una nueva sesión
SessionLocal = sessionmaker(
    autocommit=False,  # los cambios no se guardan solos; requieren db.commit()
    autoflush=False,   # los cambios no se envían a la BD hasta el commit
    bind=engine
)

# Clase base de la que heredarán todos los modelos de la app
Base = declarative_base()

# Dependencia de FastAPI — gestiona el ciclo de vida de la sesión por request
def get_db():
    db = SessionLocal()
    try:
        yield db        # FastAPI inyecta este objeto 'db' en cada endpoint
    finally:
        db.close()      # se ejecuta siempre, haya error o no