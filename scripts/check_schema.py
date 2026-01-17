# scripts/check_schema.py
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from run_auth_wrapper import app
from app import db
from app.models_user import User
from app.models_usage import UsageLedger

with app.app_context():
    i = db.inspect(db.engine)
    print("DB:", db.engine.url)
    print("Tablas:", i.get_table_names())
    if "users" in i.get_table_names():
        cols = {c["name"] for c in i.get_columns("users")}
        print("users.cols:", sorted(cols))
        u = db.session.get(User, 1)
        if u:
            print("User(1) minutes_used:", getattr(u, "minutes_used", None),
                  "minute_quota:", getattr(u, "minute_quota", None))
        else:
            print("No hay User id=1")
    if "usage_ledger" in i.get_table_names():
        rows = db.session.query(UsageLedger).order_by(UsageLedger.created_at.desc()).limit(5).all()
        for r in rows:
            print("ledger:", r.id, r.user_id, r.job_id, r.minutes_delta, r.reason, r.created_at)
