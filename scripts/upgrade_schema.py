# scripts/upgrade_schema.py
import os
import sys

# garantizar import desde el proyecto
CUR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CUR)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from run_auth_wrapper import app  # si lo tienes
except Exception:
    from app import create_app
    app = create_app()

from app import db
from sqlalchemy import inspect, text

with app.app_context():
    print("DB URL:", app.config["SQLALCHEMY_DATABASE_URI"])

    insp = inspect(db.engine)
    tables = insp.get_table_names()

    # --- users: asegurar columnas minutes_used / minute_quota
    print("== users ==")
    if "users" not in tables:
        db.create_all()
    cols = [c["name"] for c in insp.get_columns("users")]
    print("  columnas actuales:", cols)

    if "minutes_used" not in cols:
        db.session.execute(text("ALTER TABLE users ADD COLUMN minutes_used INTEGER NOT NULL DEFAULT 0"))
        print("  -> added minutes_used")
    else:
        print("  ok: minutes_used existe")

    if "minute_quota" not in cols:
        db.session.execute(text("ALTER TABLE users ADD COLUMN minute_quota INTEGER NOT NULL DEFAULT 0"))
        print("  -> added minute_quota")
    else:
        print("  ok: minute_quota existe")

    # --- usage_ledger
    print("== usage_ledger ==")
    if "usage_ledger" not in tables:
        db.create_all()
        print("  -> creada usage_ledger")
    else:
        print("  ok: usage_ledger existe")

    db.session.commit()

    print("== resumen ==")
    cols = [c["name"] for c in insp.get_columns("users")]
    print("  users ->", cols)
    print("  tablas:", insp.get_table_names())
    print("✅ Upgrade listo")
