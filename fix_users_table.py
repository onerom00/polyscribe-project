# fix_users_table.py
from __future__ import annotations
from sqlalchemy import text
from app import db

# Obtener app
try:
    from main import app  # type: ignore
except Exception:
    try:
        from app import create_app  # type: ignore
    except Exception as e:
        print("[fix_users_table] No pude importar la app:", e)
        raise
    app = create_app()  # type: ignore

REQUIRED_COLS = {
    "password_hash": "TEXT DEFAULT ''",
    "is_verified": "INTEGER DEFAULT 0",
    "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
    "last_login_at": "DATETIME"
}

def table_exists(conn) -> bool:
    q = conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    return q.fetchone() is not None

def existing_cols(conn) -> set[str]:
    rows = conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()
    # PRAGMA table_info: (cid, name, type, notnull, dflt_value, pk)
    return {r[1] for r in rows}

with app.app_context():
    with db.engine.begin() as conn:
        if not table_exists(conn):
            print("Tabla users no existe; creando todas las tablas...")
            db.create_all()
            print("✅ Tablas creadas.")
        else:
            cols = existing_cols(conn)
            to_add = [c for c in REQUIRED_COLS.keys() if c not in cols]
            if not to_add:
                print("✅ Tabla users ya tiene todas las columnas necesarias.")
            else:
                print("Faltan columnas en users:", to_add)
                for c in to_add:
                    ddl = f"ALTER TABLE users ADD COLUMN {c} {REQUIRED_COLS[c]}"
                    print("Ejecutando:", ddl)
                    conn.exec_driver_sql(ddl)
                print("✅ Columnas añadidas con éxito.")

    # (Opcional) Actualizar updated_at si no existe en filas antiguas
    try:
        with db.engine.begin() as conn:
            conn.execute(text("UPDATE users SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)"))
            conn.execute(text("UPDATE users SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))
    except Exception:
        pass

print("🏁 Migración de users completada.")
