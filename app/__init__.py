# app/__init__.py
from __future__ import annotations

import os
from flask import Flask

from app.extensions import db, migrate


def _fix_database_url(url: str) -> str:
    """
    Render a veces entrega DATABASE_URL con:
    - esquema 'postgres://'
    - salto de línea al final '\n'
    SQLAlchemy prefiere 'postgresql://'
    """
    url = (url or "").strip()  # <-- CLAVE: elimina \n y espacios
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=os.getenv("FLASK_STATIC_FOLDER", "static"),
        template_folder=os.getenv("FLASK_TEMPLATES_FOLDER", "templates"),
    )

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")

    db_url = _fix_database_url(os.getenv("DATABASE_URL", "sqlite:///polyscribe.db"))
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["APP_BASE_URL"] = os.getenv("APP_BASE_URL", "https://www.getpolyscribe.com")

    app.config["AUTH_REQUIRE_VERIFIED_EMAIL"] = os.getenv("AUTH_REQUIRE_VERIFIED_EMAIL", "1") == "1"
    app.config["DISABLE_DEVLOGIN"] = os.getenv("DISABLE_DEVLOGIN", "1") == "1"

    # SMTP
    app.config["SMTP_HOST"] = os.getenv("SMTP_HOST", "smtp.gmail.com")
    app.config["SMTP_PORT"] = int(os.getenv("SMTP_PORT", "587"))
    app.config["SMTP_USER"] = os.getenv("SMTP_USER", "")
    app.config["SMTP_PASS"] = os.getenv("SMTP_PASS", "")
    app.config["MAIL_FROM"] = os.getenv("MAIL_FROM", "PolyScribe <helppolyscribe@gmail.com>")

    # PayPal
    app.config["PAYPAL_ENV"] = os.getenv("PAYPAL_ENV", "sandbox").strip().lower()
    if app.config["PAYPAL_ENV"] == "live":
        app.config["PAYPAL_BASE_URL"] = os.getenv("PAYPAL_BASE_URL", "https://api-m.paypal.com").strip()
    else:
        app.config["PAYPAL_BASE_URL"] = os.getenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com").strip()

    app.config["PAYPAL_CLIENT_ID"] = (os.getenv("PAYPAL_CLIENT_ID") or "").strip()
    app.config["PAYPAL_CLIENT_SECRET"] = (os.getenv("PAYPAL_CLIENT_SECRET") or "").strip()
    app.config["PAYPAL_CURRENCY"] = os.getenv("PAYPAL_CURRENCY", "USD").strip()

    # IDs
    app.config["PAYPAL_PLAN_STARTER_ID"] = (os.getenv("PAYPAL_PLAN_STARTER_ID") or "").strip()
    app.config["PAYPAL_PLAN_PRO_ID"] = (os.getenv("PAYPAL_PLAN_PRO_ID") or "").strip()
    app.config["PAYPAL_PLAN_BUSINESS_ID"] = (os.getenv("PAYPAL_PLAN_BUSINESS_ID") or "").strip()
    app.config["PAYPAL_WEBHOOK_ID"] = (os.getenv("PAYPAL_WEBHOOK_ID") or "").strip()

    app.config["PAYPAL_ENABLED"] = bool(app.config["PAYPAL_CLIENT_ID"] and app.config["PAYPAL_CLIENT_SECRET"])

    app.config["FREE_TIER_MINUTES"] = int(os.getenv("FREE_TIER_MINUTES", "10"))

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Importar modelos (para que Alembic los vea)
    from app import models  # noqa: F401
    from app import models_auth  # noqa: F401
    from app import models_payment  # noqa: F401
    try:
        from app import models_user  # noqa: F401
    except Exception:
        pass

    # Blueprints
    from app.routes.pages import bp as pages_bp
    app.register_blueprint(pages_bp)

    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.routes.jobs import bp as jobs_bp
    app.register_blueprint(jobs_bp)

    from app.routes.exports import bp as exports_bp
    app.register_blueprint(exports_bp)

    from app.routes.usage import bp as usage_bp
    app.register_blueprint(usage_bp)

    # ✅ PayPal: importa SOLO lo que existe
    from app.routes.paypal import bp as paypal_bp
    app.register_blueprint(paypal_bp)

    from app.routes.pricing_page import bp as pricing_page_bp
    app.register_blueprint(pricing_page_bp)

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    return app
