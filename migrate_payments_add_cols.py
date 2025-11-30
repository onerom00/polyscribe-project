from run_auth_wrapper import app
from app import db
from sqlalchemy import text, inspect

with app.app_context():
    insp = inspect(db.engine)
    cols = {c["name"] for c in insp.get_columns("payments")}
    to_add = []
    if "amount" not in cols:
        to_add.append("ALTER TABLE payments ADD COLUMN amount REAL")
    if "currency" not in cols:
        to_add.append("ALTER TABLE payments ADD COLUMN currency TEXT")
    if "created_at" not in cols:
        to_add.append("ALTER TABLE payments ADD COLUMN created_at TEXT")

    for sql in to_add:
        db.session.execute(text(sql))
    db.session.commit()
    print("Añadidas:", to_add or "ninguna")

    # Backfill suaves (solo si existen)
    cols_after = {c["name"] for c in insp.get_columns("payments")}
    if "currency" in cols_after:
        db.session.execute(text(
            "UPDATE payments SET currency = COALESCE(NULLIF(currency,''),'USD') "
            "WHERE currency IS NULL OR currency = ''"
        ))
    if "created_at" in cols_after:
        db.session.execute(text(
            "UPDATE payments SET created_at = COALESCE(created_at, datetime('now')) "
        ))
    db.session.commit()
    print("Backfill hecho (si aplicó).")
