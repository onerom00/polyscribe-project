# scripts/create_test_user.py
import os
from app.database import Base, engine, SessionLocal
from app.models import User

# Asegura que las tablas existan
Base.metadata.create_all(bind=engine)

email = os.getenv("TEST_USER_EMAIL", "test@polyscribe.local")

s = SessionLocal()
try:
    u = s.query(User).filter_by(email=email).first()
    if not u:
        u = User(email=email)
        s.add(u)
        s.commit()
        print(f"CREATED user_id={u.id} email={u.email}")
    else:
        print(f"EXISTS  user_id={u.id} email={u.email}")
finally:
    s.close()
