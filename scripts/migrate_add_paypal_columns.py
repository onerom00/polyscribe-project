# scripts/migrate_add_paypal_columns.py
from app.database import engine
from sqlalchemy import text

def main():
    with engine.connect() as conn:
        cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(subscriptions);").fetchall()]
        def add(col, ddl):
            if col not in cols:
                print("Adding", col)
                conn.exec_driver_sql(ddl)
                conn.commit()
        add("provider", "ALTER TABLE subscriptions ADD COLUMN provider VARCHAR(32)")
        add("paypal_subscription_id", "ALTER TABLE subscriptions ADD COLUMN paypal_subscription_id VARCHAR(255)")
        add("paypal_plan_id", "ALTER TABLE subscriptions ADD COLUMN paypal_plan_id VARCHAR(255)")
        print("Done")

if __name__ == "__main__":
    main()
