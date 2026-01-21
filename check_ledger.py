from run_auth_wrapper import app
from app import db
from app.models_usage import UsageLedger
from app.models_user import User

with app.app_context():
    insp = db.inspect(db.engine)
    print("Tablas:", insp.get_table_names())
    rows = (
        db.session.query(UsageLedger)
        .order_by(UsageLedger.created_at.desc())
        .limit(10)
        .all()
    )
    for r in rows:
        print("ledger:", r.id, r.user_id, r.job_id, r.minutes_delta, r.reason, r.created_at)
    u = db.session.get(User, 1)
    print("minutes_used =", u.minutes_used)
