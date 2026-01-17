# init_db_auth.py
# Crea la tabla users sin tocar tu flujo.
from app import db
try:
    # Si tienes factory:
    from app import create_app
    app = create_app()
except Exception:
    # Si tu app expone 'app' en main.py:
    from main import app  # type: ignore

with app.app_context():
    from app.models_user import User  # importa el modelo para registrar metadata
    db.create_all()
    print("✅ Tablas creadas/actualizadas (users).")
