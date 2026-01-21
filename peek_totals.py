from run_auth_wrapper import app
from app import db
from sqlalchemy import text

with app.app_context():
    print("=== Totales por estado ===")
    for st in ("COMPLETED","captured"):
        t = db.session.execute(text(
            "SELECT COALESCE(SUM(minutes),0) FROM payments WHERE status=:st"
        ), {"st": st}).scalar()
        print(st, "=>", int(t or 0), "min")
    t_all = db.session.execute(text(
        "SELECT COALESCE(SUM(minutes),0) FROM payments WHERE status IN ('COMPLETED','captured')"
    )).scalar()
    print("TOTAL (COMPLETED|captured):", int(t_all or 0), "min")
