# scripts/migrate_audio_jobs_sqlite.py
import os
import sys
from datetime import datetime

# Asegurar imports del proyecto
CUR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CUR)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from run_auth_wrapper import app
except Exception:
    from app import create_app
    app = create_app()

from app import db
from sqlalchemy import inspect as sa_inspect  # <-- correcto

NEW_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS audio_jobs__new (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL DEFAULT '',
    audio_s3_key TEXT NOT NULL DEFAULT '',
    local_path TEXT,
    mime_type TEXT,
    size_bytes INTEGER,
    language TEXT NOT NULL DEFAULT 'auto',
    language_forced INTEGER NOT NULL DEFAULT 0,
    language_detected TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    error INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    transcript TEXT,
    summary TEXT,
    duration_seconds INTEGER,
    model_used TEXT,
    cost_cents INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

def boolish_to_int(v):
    if v in (1, "1", True, "true", "True", "TRUE", "t", "T", "yes", "YES", "y", "Y"):
        return 1
    return 0

def to_int_or_none(v):
    if v in (None, "", b""):
        return None
    try:
        return int(v)
    except Exception:
        return None

def to_dt_str(v):
    if v is None or v == "":
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    return str(v)

with app.app_context():
    eng = db.engine
    insp = sa_inspect(eng)
    tables = insp.get_table_names()

    if "audio_jobs" not in tables:
        print("No existe tabla 'audio_jobs'. Nada que migrar.")
        sys.exit(0)

    print("Migrando 'audio_jobs' → 'audio_jobs__new' ...")

    with eng.begin() as conn:
        # 1) crear nueva tabla
        conn.exec_driver_sql("PRAGMA foreign_keys = OFF;")
        conn.exec_driver_sql(NEW_SCHEMA_SQL)

        # 2) leer datos de la tabla antigua
        res = conn.exec_driver_sql("SELECT * FROM audio_jobs")
        cols = list(res.keys())
        print("Columnas antiguas:", cols)

        ins_sql = """
INSERT INTO audio_jobs__new (
    id, user_id, filename, original_filename, audio_s3_key, local_path,
    mime_type, size_bytes, language, language_forced, language_detected,
    status, error, error_message, transcript, summary, duration_seconds,
    model_used, cost_cents, created_at, updated_at
) VALUES (
    :id, :user_id, :filename, :original_filename, :audio_s3_key, :local_path,
    :mime_type, :size_bytes, :language, :language_forced, :language_detected,
    :status, :error, :error_message, :transcript, :summary, :duration_seconds,
    :model_used, :cost_cents, :created_at, :updated_at
);
"""

        n = 0
        for row in res:
            r = dict(zip(cols, row))

            payload = {
                "id": str(r.get("id")),
                "user_id": to_int_or_none(r.get("user_id")) or 0,
                "filename": (r.get("filename") or "").strip() or "file",
                "original_filename": (r.get("original_filename") or ""),
                "audio_s3_key": (r.get("audio_s3_key") or ""),
                "local_path": r.get("local_path"),
                "mime_type": r.get("mime_type"),
                "size_bytes": to_int_or_none(r.get("size_bytes")),
                "language": (r.get("language") or "auto"),
                "language_forced": boolish_to_int(r.get("language_forced")),
                "language_detected": r.get("language_detected"),
                "status": (r.get("status") or "queued"),
                "error": boolish_to_int(r.get("error")),
                "error_message": r.get("error_message"),
                "transcript": r.get("transcript"),
                "summary": r.get("summary"),
                "duration_seconds": to_int_or_none(r.get("duration_seconds")),
                "model_used": r.get("model_used"),
                "cost_cents": to_int_or_none(r.get("cost_cents")),
                "created_at": to_dt_str(r.get("created_at")),
                "updated_at": to_dt_str(r.get("updated_at")),
            }

            conn.exec_driver_sql(ins_sql, payload)
            n += 1

        print(f"Copiadas {n} filas.")

        # 3) reemplazar tablas
        conn.exec_driver_sql("DROP TABLE audio_jobs;")
        conn.exec_driver_sql("ALTER TABLE audio_jobs__new RENAME TO audio_jobs;")
        conn.exec_driver_sql("PRAGMA foreign_keys = ON;")

    print("✅ Migración de 'audio_jobs' completada.")
