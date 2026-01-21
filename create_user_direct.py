# create_user_direct.py
from __future__ import annotations
import sys
from typing import Any, Dict

from sqlalchemy import text
from app import db

# Carga app desde main o factory
try:
    from main import app  # type: ignore
except Exception:
    try:
        from app import create_app  # type: ignore
    except Exception as e:
        print("[create_user_direct] No pude importar la app:", e)
        sys.exit(1)
    app = create_app()  # type: ignore


def make_hash(password: str) -> str:
    """Genera hash compatible con tu modelo si existe set_password; si no, usa Werkzeug (scrypt)."""
    try:
        from app.models_user import User  # type: ignore
        u = User()
        if hasattr(u, "set_password"):
            u.set_password(password)
            h = getattr(u, "password_hash", None)
            if h:
                return h
    except Exception:
        pass
    try:
        from werkzeug.security import generate_password_hash
        return generate_password_hash(password, method="scrypt")
    except Exception:
        from werkzeug.security import generate_password_hash
        return generate_password_hash(password)


def get_users_columns(conn) -> Dict[str, tuple]:
    """Devuelve dict: nombre_columna -> fila PRAGMA (cid,name,type,notnull,dflt_value,pk)"""
    rows = conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()
    return {r[1]: r for r in rows}


def main():
    if len(sys.argv) < 3:
        print("Uso: python create_user_direct.py <email> <password>")
        sys.exit(2)

    email = sys.argv[1].strip().lower()
    password = sys.argv[2]
    phash = make_hash(password)

    # Defaults robustos para NOT NULL que vimos en tu tabla
    DEFAULTS: Dict[str, Any] = {
        "plan_tier": "free",
        "minute_quota": 0,   # cuota en minutos del plan (ajusta si quieres)
        "minutes_used": 0,   # usados
        "is_active": 1,      # activo
        "is_verified": 1,    # verificado
        "role": "user",      # si existe
        "status": "active",  # si existe
    }

    with app.app_context():
        with db.engine.begin() as conn:
            cols = get_users_columns(conn)
            if not cols:
                print("❌ No encuentro tabla 'users'.")
                sys.exit(3)

            params: Dict[str, Any] = {"email": email}

            # password + flags principales si existen
            if "password_hash" in cols:       params["password_hash"] = phash
            if "is_verified" in cols:         params["is_verified"] = DEFAULTS["is_verified"]
            if "plan_tier" in cols:           params["plan_tier"]   = DEFAULTS["plan_tier"]
            if "minute_quota" in cols:        params["minute_quota"]= DEFAULTS["minute_quota"]
            if "minutes_used" in cols:        params["minutes_used"]= DEFAULTS["minutes_used"]
            if "is_active" in cols:           params["is_active"]   = DEFAULTS["is_active"]
            if "role" in cols:                params["role"]        = DEFAULTS["role"]
            if "status" in cols:              params["status"]      = DEFAULTS["status"]

            # display_name si existe (opcional)
            if "display_name" in cols:
                local_part = email.split("@")[0] if "@" in email else email
                params["display_name"] = local_part

            have_created = "created_at" in cols
            have_updated = "updated_at" in cols

            # ¿Existe ya?
            row = conn.exec_driver_sql(
                "SELECT id FROM users WHERE email = :email LIMIT 1", {"email": email}
            ).fetchone()

            if row:
                # UPDATE dinámico
                set_parts = []
                for k in params:
                    if k == "email": 
                        continue
                    set_parts.append(f"{k} = :{k}")
                if have_updated:
                    set_parts.append("updated_at = CURRENT_TIMESTAMP")
                sql = f"UPDATE users SET {', '.join(set_parts)} WHERE email = :email"
                conn.exec_driver_sql(sql, params)
                print(f"✅ Usuario ACTUALIZADO/verificado: {email}")
            else:
                # INSERT dinámico
                insert_cols = list(params.keys())
                values_parts = [f":{c}" for c in insert_cols]
                if have_created:
                    insert_cols.append("created_at")
                    values_parts.append("CURRENT_TIMESTAMP")
                if have_updated:
                    insert_cols.append("updated_at")
                    values_parts.append("CURRENT_TIMESTAMP")
                sql = f"INSERT INTO users ({', '.join(insert_cols)}) VALUES ({', '.join(values_parts)})"
                conn.exec_driver_sql(sql, params)
                print(f"✅ Usuario CREADO/verificado: {email}")


if __name__ == "__main__":
    main()
