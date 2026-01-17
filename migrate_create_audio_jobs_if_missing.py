from run_auth_wrapper import app
from app import db
from sqlalchemy import text, inspect

DDL = """
CREATE TABLE audio_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    filename TEXT,
    language TEXT,
    error TEXT,
    summary TEXT,
    original_filename TEXT,
    audio_s3_key TEXT,
    local_path TEXT,
    mime_type TEXT,
    size_bytes INTEGER,
    status TEXT,
    error_message TEXT,
    language_forced TEXT,
    language_detected TEXT,
    duration_seconds INTEGER,
    model_used TEXT,
    transcript TEXT,
    cost_cents INTEGER,
    created_at DATETIME,
    updated_at DATETIME
)
"""

with app.app_context():
    insp = inspect(db.engine)
    names = set(insp.get_table_names())
    if "audio_jobs" not in names:
        db.session.execute(text(DDL))
        db.session.commit()
        print("CREATED: audio_jobs")
    else:
        print("OK: audio_jobs already exists")
