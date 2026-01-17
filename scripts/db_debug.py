from app.database import engine, SessionLocal
from app.models import Subscription, UsageLedger, User

def main():
    print("ENGINE URL:", engine.url)
    s = SessionLocal()
    try:
        users = s.query(User).all()
        print("Users:", [(u.id, u.email) for u in users])

        subs = s.query(Subscription).all()
        print("Subscriptions:", [
            (x.id, x.user_id, x.plan, x.status, x.provider, x.paypal_plan_id, x.paypal_subscription_id)
            for x in subs
        ])

        ledgers = s.query(UsageLedger).all()
        print("Ledgers:", [(l.user_id, l.month_key, l.seconds) for l in ledgers])
    finally:
        s.close()

if __name__ == "__main__":
    main()
