from run_auth_wrapper import app
from app import db
from sqlalchemy import text

with app.app_context():
    # 1) Usuario
    u = db.session.execute(text("SELECT id,email,plan_tier,minute_quota,minutes_used FROM users WHERE id=1")).mappings().first()
    print("USER:", dict(u) if u else None)

    # 2) Pagos
    pays = db.session.execute(text("SELECT order_id,status,amount,currency,minutes FROM payments ORDER BY rowid DESC LIMIT 10")).mappings().all()
    print("PAYMENTS:")
    for p in pays:
        print(" ", dict(p))
