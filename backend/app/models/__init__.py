"""
SQLAlchemy models, one module per spec section. Every table's docstring states what personal
data (if any) it holds and its retention period, per the spec's privacy-by-design requirement
(Part 2.6). Import all modules here so Alembic autogenerate and Base.metadata.create_all see
every table.
"""

from app.models import (  # noqa: F401
    audit,
    jurisdiction,
    module1_violations,
    module2_corruption,
    module3_infra,
    module4_emergency,
    officials,
    station,
    users,
)
