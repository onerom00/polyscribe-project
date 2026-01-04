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

    # -----------------------------
    # CONFIG GENERAL
    # -----------------------------
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        "sqlite:///polyscribe3.db",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Cookies de sesión (PROD friendly)
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    # Si estás 100% en https, puedes ponerlo en 1:
    app.config["SESSION_COOKIE_SECURE"] = bool(int(os.getenv("SESSION_COOKIE_SECURE", "0")))

    # URL base pública
    app.config["APP_BASE_URL"] = os.getenv(
        "APP_BASE_URL",
        "https://getpolyscribe.com",
    )

    # Auth gating
    app.config["AUTH_REQUIRE_VERIFIED_EMAIL"] = bool(int(os.getenv("AUTH_REQUIRE_VERIFIED_EMAIL", "1")))

    # PayPal (mantengo tu config)
    app.config["PAYPAL_ENV"] = os.getenv("PAYPAL_ENV", "sandbox")
    app.config["PAYPAL_BASE_URL"] = os.getenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")
    app.config["PAYPAL_CLIENT_ID"] = os.getenv("PAYPAL_CLIENT_ID")
    app.config["PAYPAL_CLIENT_SECRET"] = os.getenv("PAYPAL_CLIENT_SECRET")
    app.config["PAYPAL_CURRENCY"] = os.getenv("PAYPAL_CURRENCY", "USD")
    app.config["PAYPAL_WEBHOOK_ID"] = os.getenv("PAYPAL_WEBHOOK_ID")

    app.config["PAYPAL_ENABLED"] = bool(app.config["PAYPAL_CLIENT_ID"] and app.config["PAYPAL_CLIENT_SECRET"])
    app.config["FREE_TIER_MINUTES"] = int(os.getenv("FREE_TIER_MINUTES", "10"))

    # -----------------------------
    # EXTENSIONES
    # -----------------------------
    db.init_app(app)
    migrate.init_app(app, db)

    # Importar modelos (para que SQLAlchemy los registre)
    from app import models  # noqa: F401
    from app import models_payment  # noqa: F401
    from app.models_user import User  # noqa: F401

    # -----------------------------
    # BLUEPRINTS
    # -----------------------------
    from app.routes.pages import bp as pages_bp
    app.register_blueprint(pages_bp)

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

    # ✅ AUTH PROD
    from app.routes.auth_prod import bp as auth_bp
    app.register_blueprint(auth_bp)

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    # En producción usa migraciones, pero esto ayuda en sqlite simple
    with app.app_context():
        db.create_all()

    return app
