# app/database.py
"""
Capa de base de datos para la app.
Expone:
  - db: instancia global de SQLAlchemy
  - init_db(app): inicializa SQLAlchemy con la app
"""

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData

# Convenciones de nombres (útil para migraciones y SQLite)
metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)

# <- ESTO es lo que faltaba: exportamos 'db'
db = SQLAlchemy(metadata=metadata)


def init_db(app):
    """Inicializa la instancia global de SQLAlchemy con la app Flask."""
    db.init_app(app)
