from run_auth_wrapper import app
from app import db
from sqlalchemy import text

with app.app_context():
    # Intenta castear amount_value -> REAL (sustituye coma por punto por si acaso)
    db.session.execute(text(
        "UPDATE payments "
        "SET amount = CAST(REPLACE(amount_value, ',', '.') AS REAL) "
        "WHERE (amount IS NULL OR amount = 0) AND amount_value IS NOT NULL AND amount_value <> ''"
    ))
    # Asegura currency
    db.session.execute(text(
        "UPDATE payments SET currency = COALESCE(NULLIF(currency,''),'USD') "
        "WHERE currency IS NULL OR currency = ''"
    ))
    db.session.commit()
    print("Backfill de amount y currency completado.")
