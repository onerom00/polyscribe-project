import os, re, sqlite3

DB_URL = os.getenv("DATABASE_URL", "sqlite:///app.db")

if not DB_URL.startswith("sqlite:///"):
    raise SystemExit("Esta utilidad solo soporta SQLite (DATABASE_URL=sqlite:///ruta/al/archivo.db).")

DB_PATH = DB_URL[len("sqlite:///"):]  # quita el prefijo
print("Usando DB:", DB_PATH)

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

def has_column(table, col):
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())

changes = []

# Agrega lo que tu modelo mapea y puede faltar:
to_add = [
    ("summary", "TEXT"),
    ("transcript", "TEXT"),
    ("language_detected", "VARCHAR(8)"),
]

for col, typ in to_add:
    if not has_column("audio_jobs", col):
        sql = f"ALTER TABLE audio_jobs ADD COLUMN {col} {typ}"
        print("->", sql)
        cur.execute(sql)
        changes.append(col)

con.commit()
con.close()

print("OK. Columnas agregadas:", ", ".join(changes) if changes else "ninguna (ya existían)")
