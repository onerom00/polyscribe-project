import os, traceback
from sqlalchemy import inspect
from run_auth_wrapper import app
from app import db

print("SQLALCHEMY_DATABASE_URI:", app.config.get("SQLALCHEMY_DATABASE_URI"))
uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
if uri.startswith("sqlite:///"):
    # ruta relativa → resolvemos a absoluta
    rel = uri.replace("sqlite:///", "", 1)
    print("SQLite (relativa) → absoluta:", os.path.abspath(rel))
elif uri.startswith("sqlite:////"):
    print("SQLite (absoluta):", uri)

# Importa modelos; si falla, muestra el error (no lo ocultamos)
def safe_import(label, mod, name):
    try:
        m = __import__(mod, fromlist=[name])
        getattr(m, name)
        print(f"OK import {label}")
    except Exception as e:
        print(f"ERROR import {label}:", e)
        traceback.print_exc()

safe_import("User", "app.models_user", "User")
safe_import("AudioJob", "app.models_job", "AudioJob")
safe_import("Payment", "app.models_payment", "Payment")

with app.app_context():
    db.create_all()
    insp = inspect(db.engine)
    tables = insp.get_table_names()
    print("Tablas ahora:", tables)
    print("Tiene audio_jobs?:", insp.has_table("audio_jobs"))
    print("Tiene payments?:", insp.has_table("payments"))
