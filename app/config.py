import os
from sqlalchemy.engine.url import make_url

class Config:
    # Secret
    SECRET_KEY = os.getenv('SECRET_KEY') or os.getenv('FLASK_SECRET_KEY', 'change-me')

    # DB: default por SO si no hay env
    default_db = "sqlite:///app.db" if os.name == "nt" else "sqlite:////var/data/app.db"
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', default_db)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Uso
    FREE_TIER_MINUTES = int(os.getenv('FREE_TIER_MINUTES', '10'))
    BILLING_PLAN_MINUTES = int(os.getenv('BILLING_PLAN_MINUTES', '120'))

    # S3 (acepta tus nombres)
    AWS_REGION = os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION')
    AWS_S3_BUCKET = os.getenv('AWS_S3_BUCKET') or os.getenv('S3_BUCKET')

    # PayPal (acepta tus nombres)
    PAYPAL_MODE = os.getenv('PAYPAL_MODE') or os.getenv('PAYPAL_ENV', 'sandbox')
    PAYPAL_CLIENT_ID = os.getenv('PAYPAL_CLIENT_ID')
    PAYPAL_SECRET = os.getenv('PAYPAL_SECRET') or os.getenv('PAYPAL_CLIENT_SECRET')
    PAYPAL_PLAN_ID = os.getenv('PAYPAL_PLAN_ID') or os.getenv('PAYPAL_PLAN_BASIC_ID')
    PAYPAL_WEBHOOK_ID = os.getenv('PAYPAL_WEBHOOK_ID')
    PAYPAL_BASE_URL = os.getenv('PAYPAL_BASE_URL', 'https://api-m.sandbox.paypal.com')


# --- Opcional: asegurar carpeta del archivo SQLite (evita "unable to open database file")
def _ensure_sqlite_dir(uri: str):
    try:
        url = make_url(uri)
        if url.get_backend_name() == "sqlite":
            db_path = url.database
            if db_path and db_path not in (":memory:",):
                directory = os.path.dirname(db_path)
                if directory and not os.path.exists(directory):
                    os.makedirs(directory, exist_ok=True)
    except Exception:
        pass

_ensure_sqlite_dir(Config.SQLALCHEMY_DATABASE_URI)
