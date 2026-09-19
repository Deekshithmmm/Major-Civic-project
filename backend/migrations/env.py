from logging.config import fileConfig

from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.database import Base
from app import models  # noqa: F401  (ensures all model modules register on Base.metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata

# PostGIS installs its own tables (spatial_ref_sys) and, in the postgis/postgis image, the
# tiger geocoder and topology schemas. Without this filter, autogenerate treats every one of
# them as a table we deleted and emits DROP statements that would break the extension.
POSTGIS_SCHEMAS = {"tiger", "tiger_data", "topology"}


def include_object(object_, name, type_, reflected, compare_to):
    schema = getattr(object_, "schema", None)
    if schema in POSTGIS_SCHEMAS:
        return False
    if type_ == "table" and reflected and name not in target_metadata.tables:
        return False
    if type_ == "index":
        table = getattr(object_, "table", None)
        if table is not None and table.name not in target_metadata.tables:
            return False
    # GeoAlchemy2's own filter handles the spatial indexes/columns it manages internally.
    return alembic_helpers.include_object(object_, name, type_, reflected, compare_to)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        render_item=alembic_helpers.render_item,
        process_revision_directives=alembic_helpers.writer,
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
            target_metadata=target_metadata,
            include_object=include_object,
            render_item=alembic_helpers.render_item,
            process_revision_directives=alembic_helpers.writer,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
