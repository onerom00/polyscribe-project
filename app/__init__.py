# app/__init__.py
from __future__ import annotations

import os
from flask import Flask

from app.extensions import db, migrate


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=os.getenv("FLASK_STATIC_FOLDER", "static"),
        template_folder=os.getenv("FLASK_TEMPLATES_FOLDER", "templates"),
    )

    # -----------------------------------------------------------
    # CONFIG GENERAL
    # -----------------------------------------------------------
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        "sqlite:///polyscribe3.db",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # -----------------------------------------------------------
    # URL base (IMPORTANTE: usa www)
    # -----------------------------------------------------------
    app.config["APP_BASE_URL"] = os.getenv(
        "APP_BASE_URL",
        "https://www.getpolyscribe.com",
    )

    # -----------------------------------------------------------
    # FLAGS AUTH
    # -----------------------------------------------------------
    app.config["AUTH_REQUIRE_VERIFIED_EMAIL"] = os.getenv("AUTH_REQUIRE_VERIFIED_EMAIL", "1") == "1"
    app.config["DISABLE_DEVLOGIN"] = os.getenv("DISABLE_DEVLOGIN", "1") == "1"

    # -----------------------------------------------------------
    # SMTP (Gmail app password)
    # -----------------------------------------------------------
    app.config["SMTP_HOST"] = os.getenv("SMTP_HOST", "smtp.gmail.com")
    app.config["SMTP_PORT"] = int(os.getenv("SMTP_PORT", "587"))
    app.config["SMTP_USER"] = os.getenv("SMTP_USER", "")
    app.config["SMTP_PASS"] = os.getenv("SMTP_PASS", "")
    app.config["MAIL_FROM"] = os.getenv("MAIL_FROM", "PolyScribe <helppolyscribe@gmail.com>")

    # -----------------------------------------------------------
    # PAYPAL (como ya lo tenías)
    # -----------------------------------------------------------
    app.config["PAYPAL_ENV"] = os.getenv("PAYPAL_ENV", "sandbox")
    app.config["PAYPAL_BASE_URL"] = os.getenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")
    app.config["PAYPAL_CLIENT_ID"] = os.getenv("PAYPAL_CLIENT_ID")
    app.config["PAYPAL_CLIENT_SECRET"] = os.getenv("PAYPAL_CLIENT_SECRET")
    app.config["PAYPAL_CURRENCY"] = os.getenv("PAYPAL_CURRENCY", "USD")
    app.config["PAYPAL_PLAN_STARTER_ID"] = os.getenv("PAYPAL_PLAN_STARTER_ID", "P-9W9394623R721322BNEW7GUY")
    app.config["PAYPAL_WEBHOOK_ID"] = os.getenv("PAYPAL_WEBHOOK_ID")
    app.config["PAYPAL_ENABLED"] = bool(app.config["PAYPAL_CLIENT_ID"] and app.config["PAYPAL_CLIENT_SECRET"])

    app.config["FREE_TIER_MINUTES"] = int(os.getenv("FREE_TIER_MINUTES", "10"))

    # -----------------------------------------------------------
    # EXTENSIONS
    # -----------------------------------------------------------
    db.init_app(app)
    migrate.init_app(app, db)

    # Importar modelos (asegura tablas/migraciones)
    from app import models  # noqa: F401
    from app import models_payment  # noqa: F401
    from app import models_user  # noqa: F401  <-- IMPORTANTE

    # -----------------------------------------------------------
    # BLUEPRINTS
    # -----------------------------------------------------------
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

    from app.routes.paypal import bp as paypal_bp, api_bp as paypal_api_bp
    app.register_blueprint(paypal_bp)
    app.register_blueprint(paypal_api_bp)

    from app.routes.pricing_page import bp as pricing_page_bp
    app.register_blueprint(pricing_page_bp)

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    with app.app_context():
        db.create_all()

    return app
