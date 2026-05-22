from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from app.config import get_settings
from app.database import Base

# Se importan todos los modelos aquí para que Alembic los detecte
from app.auth.models import User
from app.inventory.models import InventoryItem, InventoryEvent
from app.notifications.models import DeviceToken, NotificationPreference, NotificationDispatch
from app.recipes.models import Recipe, RecipeIngredient, RecipeInteraction
from app.sync.models import SyncLog
from app.telemetry.models import ScanEvent, ExpiryAccuracyEvent, ScreenEvent
from app.analytics.models import AnalyticsEvent
from app.shopping_list.models import ShoppingItem

config = context.config
settings = get_settings()

# Inyecta la DATABASE_URL desde el .env en vez de leerla del alembic.ini
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Le dice a Alembic qué modelos debe rastrear para generar migraciones
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()