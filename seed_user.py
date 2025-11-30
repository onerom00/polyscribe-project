from run_auth_wrapper import app
from app import db
from werkzeug.security import generate_password_hash
from app.models_user import User

EMAIL = "tu@correo.com"
PASS  = "Secreta123!"

with app.app_context():
    u = db.session.query(User).filter(User.email==EMAIL).first()
    if not u:
        u = User(
            email=EMAIL,
            password_hash=generate_password_hash(PASS),
            is_verified=True
        )
        # Si tu modelo tiene NOT NULLs, rellénalos:
        defaults = {
            "plan_tier": "free",
            "minute_quota": 0,
            "minutes_used": 0,
            "is_active": True
        }
        for k,v in defaults.items():
            if hasattr(u,k) and getattr(u,k) is None:
                setattr(u,k,v)
        db.session.add(u)
        db.session.commit()
        print("Usuario creado:", EMAIL)
    else:
        print("Usuario ya existe:", EMAIL)
