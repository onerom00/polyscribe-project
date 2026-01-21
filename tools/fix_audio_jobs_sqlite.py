import sqlite3
import os

DB_PATH = os.environ.get("DATABASE_FILE", "polyscribe.db")

ddl_new = """
CREATE TABLE audio_jobs_new (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  filename TEXT,
  original_filename TEXT,
  audio_s3_key TEXT DEFAULT '',
  local_path TEXT,
  mime_type TEXT,
  size_bytes INTEGER,
  language TEXT DEFAULT 'auto',
  language_forced BOOLEAN NOT NULL DEFAULT 0,
  language_detected TEXT,
  status TEXT DEFAULT 'done',
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

copy_sql = """
INSERT INTO audio_jobs_new(
  id,user_id,filename,original_filename,audio_s3_key,local_path,mime_type,size_bytes,
  language,language_forced,language_detected,status,error,error_message,transcript,
  summary,duration_seconds,model_used,cost_cents,created_at,updated_at
)
SELECT
  id,user_id,filename,original_filename,audio_s3_key,local_path,mime_type,size_bytes,
  language,COALESCE(language_forced,0),language_detected,status,COALESCE(error,0),error_message,transcript,
  summary,duration_seconds,model_used,cost_cents,created_at,updated_at
FROM audio_jobs;
"""

def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("PRAGMA foreign_keys=OFF;")
    con.commit()

    # crea tabla nueva
    cur.execute(ddl_new)
    con.commit()

    # copia datos si existe tabla vieja
    try:
        cur.execute(copy_sql)
        con.commit()
    except Exception as e:
        print("Aviso al copiar (puede ser tabla vacía):", e)

    # renombra
    cur.execute("DROP TABLE audio_jobs;")
    con.commit()
    cur.execute("ALTER TABLE audio_jobs_new RENAME TO audio_jobs;")
    con.commit()
    con.close()
    print("OK: tabla audio_jobs reparada.")

if __name__ == "__main__":
    main()
