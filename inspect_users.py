# inspect_users.py
from __future__ import annotations
from app import db

try:
    from main import app  # type: ignore
except Exception:
    from app import create_app  # type: ignore
    app = create_app()  # type: ignore

def main() -> None:
    with app.app_context():
        cols = db.session.execute(db.text("PRAGMA table_info(users)")).fetchall()
        print("== Columnas users ==")
        for c in cols:
            # (cid, name, type, notnull, dflt_value, pk)
            print(f"- {c[1]}  {c[2]}  NOTNULL={c[3]}  DEF={c[4]}  PK={c[5]}")

        print("\n== Filas ==")
        rows = db.session.execute(db.text("SELECT * FROM users")).fetchall()
        if not rows:
            print("(sin filas)")
        for r in rows:
            d = dict(r._mapping)
            email = d.get("email")
            verified = d.get("is_verified")
            plan = d.get("plan_tier") or d.get("plan") or d.get("tier")
            print(f"- {email}  verified={verified}  plan={plan}")

if __name__ == "__main__":
    main()
