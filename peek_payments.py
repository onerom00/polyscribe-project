from run_auth_wrapper import app
from app import db
from sqlalchemy import text, inspect

with app.app_context():
    # Descubrir columnas reales en 'payments'
    insp = inspect(db.engine)
    cols = [c["name"] for c in insp.get_columns("payments")]
    print("COLUMNS:", cols)

    base = ["order_id","status","minutes"]          # las que nos importan
    extras = [c for c in ["amount","currency","created_at","created","updated_at"] if c in cols]
    sel = [c for c in base + extras if c in cols]
    if not sel:
        sel = cols or ["rowid"]  # último recurso

    sql = f"SELECT {','.join(sel)} FROM payments ORDER BY rowid DESC LIMIT 20"
    rows = db.session.execute(text(sql)).mappings().all()
    print("PAYMENTS:")
    for r in rows:
        print(dict(r))

    total = db.session.execute(text(
        "SELECT COALESCE(SUM(minutes),0) FROM payments WHERE status IN ('COMPLETED','captured')"
    )).scalar()
    print("TOTAL_MIN:", int(total or 0))

    # Mostrar el SQL de creación por claridad
    ddl = db.session.execute(text(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='payments'"
    )).scalar()
    print("\nDDL payments:\n", ddl)
