# tools/create_dev_user.py
import os
import sys
from pathlib import Path

# 1) Asegurar que el root del proyecto esté en sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 2) Cargar app y ORM
from app import create_app, db
from app.models import User           # registra los modelos en la metadata de Base
from app.database import Base         # <-- tus modelos heredan de este Base
from sqlalchemy import inspect

def main():
    # Usar la misma URI que la app (o .env)
    os.environ.setdefault("DATABASE_URL", "sqlite:///polyscribe.db")

    app = create_app()
    uri = os.getenv("DATABASE_URL", app.config.get("SQLALCHEMY_DATABASE_URI"))
    print("DB URI =>", uri)

    with app.app_context():
        # 3) Crear tablas de modelos que heredan de Base (SQLAlchemy puro)
        Base.metadata.create_all(bind=db.engine)

        # (opcional) si también tienes modelos con db.Model, descomenta:
        # db.create_all()

        # Mostrar tablas para verificar
        insp = inspect(db.engine)
        print("Tablas:", insp.get_table_names())

        # 4) Crear / asegurar usuario DEV
        uid = int(os.getenv("DEV_USER_ID", "2"))
        email = os.getenv("DEV_USER_EMAIL", f"dev{uid}@local")
        name = os.getenv("DEV_USER_NAME", "Dev User")
        free_minutes = int(os.getenv("FREE_TIER_MINUTES", "10"))

        u = db.session.get(User, uid)
        if not u:
            u = User(
                id=uid,
                email=email,
                display_name=name,
                plan_tier="free",
                minute_quota=free_minutes,
                minutes_used=0,
                is_active=True,
            )
            db.session.add(u)
            db.session.commit()
            print(f"✔ Usuario creado: id={u.id} email={u.email}")
        else:
            print(f"✔ Usuario ya existe: id={u.id} email={u.email}")

if __name__ == "__main__":
    main()
