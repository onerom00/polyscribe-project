# create_user.py
from __future__ import annotations
import sys
from typing import Any

from app import db

# Obtener la app
try:
    from main import app  # type: ignore
except Exception:
    try:
        from app import create_app  # type: ignore
    except Exception as e:
        print("[create_user] No pude importar la app:", e)
        sys.exit(1)
    app = create_app()  # type: ignore

from app.models_user import User  # tu modelo

def _set_password(u: Any, password: str) -> None:
    if hasattr(u, "set_password"):
        u.set_password(password)
    elif hasattr(u, "password_hash"):
        setattr(u, "password_hash", password)
    else:
        raise RuntimeError("El modelo User no tiene set_password ni password_hash")

def _ensure_plan_tier(u: Any) -> None:
    """
    Asigna 'free' al atributo ORM que mapea a la columna plan_tier,
    aunque el nombre del atributo sea distinto (p.ej. 'plan').
    """
    from sqlalchemy.inspection import inspect
    mapper = inspect(type(u))

    # 1) Buscar por nombres comunes de atributo
    candidate_attr_names = ["plan_tier", "plan", "tier", "subscription_tier", "plan_name"]
    for name in candidate_attr_names:
        if name in mapper.attrs.keys():
            setattr(u, name, getattr(u, name, None) or "free")
            return

    # 2) Buscar por nombre de COLUMNA 'plan_tier' y setear por su clave ORM
    for col in mapper.columns:
        if col.name == "plan_tier":
            setattr(u, col.key, getattr(u, col.key, None) or "free")
            return

    # 3) Como última opción, si hay algún atributo que contenga 'plan' en el nombre, úsalo
    for attr in mapper.attrs.keys():
        if "plan" in attr:
            setattr(u, attr, getattr(u, attr, None) or "free")
            return

    # Si llegamos aquí, no encontramos dónde setearlo; lo avisamos claramente
    raise RuntimeError(
        "No encontré un atributo ORM para la columna 'plan_tier'. "
        "Revisa tu app.models_user.User: define un campo para el plan o pásame el modelo y lo ajustamos."
    )

def _set_if_exists(u: Any, name: str, value: Any) -> None:
    if hasattr(u, name):
        cur = getattr(u, name)
        if cur in (None, ""):
            setattr(u, name, value)

def main():
    if len(sys.argv) < 3:
        print("Uso: python create_user.py <email> <password>")
        sys.exit(2)

    email = sys.argv[1].strip().lower()
    password = sys.argv[2]

    with app.app_context():
        u = db.session.query(User).filter(User.email == email).first()
        if not u:
            u = User(email=email)
            _set_password(u, password)
            _set_if_exists(u, "is_verified", True)
            # Defaults útiles si existen en tu modelo
            for k, v in {
                "role": "user",
                "status": "active",
                "minutes_balance": 0,
                "usage_seconds": 0,
                "allowance_seconds": 0,
            }.items():
                _set_if_exists(u, k, v)
            # Imprescindible para tu esquema:
            _ensure_plan_tier(u)

            db.session.add(u)
        else:
            _set_password(u, password)
            _set_if_exists(u, "is_verified", True)
            # Asegura plan_tier también en updates
            try:
                _ensure_plan_tier(u)
            except Exception as e:
                print("[create_user] Aviso:", e)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            # Mostrar qué valores llevamos justo antes de fallar
            try:
                from sqlalchemy.inspection import inspect
                mapper = inspect(type(u))
                dump = {attr: getattr(u, attr, None) for attr in mapper.attrs.keys()}
                print("[create_user] Estado del usuario previo al commit:", dump)
            except Exception:
                pass
            raise
        print(f"✅ Usuario listo y verificado: {email}")

if __name__ == "__main__":
    main()
