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

    # ---------------------------------------------------------
    # 🔐 Seguridad básica
    # ---------------------------------------------------------
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("SECRET_KEY is not set")

    # ---------------------------------------------------------
    # 🗄️ DATABASE (ÚNICA FUENTE DE VERDAD)
    # ---------------------------------------------------------
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    # Render antiguamente usaba postgres:// (no permitido en SQLAlchemy >=2)
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # ---------------------------------------------------------
    # 🌐 App base
    # ---------------------------------------------------------
    app.config["APP_BASE_URL"] = os.getenv(
        "APP_BASE_URL",
        "https://www.getpolyscribe.com",
    )

    # ---------------------------------------------------------
    # 🔐 Auth
    # ---------------------------------------------------------
    app.config["AUTH_REQUIRE_VERIFIED_EMAIL"] = os.getenv(
        "AUTH_REQUIRE_VERIFIED_EMAIL", "1"
    ) == "1"

    app.config["DISABLE_DEVLOGIN"] = os.getenv(
        "DISABLE_DEVLOGIN", "1"
    ) == "1"

    # ---------------------------------------------------------
    # ✉️ SMTP
    # ---------------------------------------------------------
    app.config["SMTP_HOST"] = os.getenv("SMTP_HOST", "smtp.gmail.com")
    app.config["SMTP_PORT"] = int(os.getenv("SMTP_PORT", "587"))
    app.config["SMTP_USER"] = os.getenv("SMTP_USER", "")
    app.config["SMTP_PASS"] = os.getenv("SMTP_PASS", "")
    app.config["MAIL_FROM"] = os.getenv(
        "MAIL_FROM",
        "PolyScribe <helppolyscribe@gmail.com>",
    )

    # ---------------------------------------------------------
    # 💰 PayPal
    # ---------------------------------------------------------
    app.config["PAYPAL_ENV"] = os.getenv("PAYPAL_ENV", "live")
    app.config["PAYPAL_BASE_URL"] = os.getenv(
        "PAYPAL_BASE_URL",
        "https://api-m.paypal.com",
    )

    app.config["PAYPAL_CLIENT_ID"] = os.getenv("PAYPAL_CLIENT_ID")
    app.config["PAYPAL_CLIENT_SECRET"] = os.getenv("PAYPAL_CLIENT_SECRET")
    app.config["PAYPAL_CURRENCY"] = os.getenv("PAYPAL_CURRENCY", "USD")
    app.config["PAYPAL_PLAN_STARTER_ID"] = os.getenv("PAYPAL_PLAN_STARTER_ID")
    app.config["PAYPAL_WEBHOOK_ID"] = os.getenv("PAYPAL_WEBHOOK_ID")

    app.config["PAYPAL_ENABLED"] = bool(
        app.config["PAYPAL_CLIENT_ID"]
        and app.config["PAYPAL_CLIENT_SECRET"]
    )

    # ---------------------------------------------------------
    # ⏱️ Límites
    # ---------------------------------------------------------
    app.config["FREE_TIER_MINUTES"] = int(
        os.getenv("FREE_TIER_MINUTES", "10")
    )

    # ---------------------------------------------------------
    # 🔌 Extensions
    # ---------------------------------------------------------
    db.init_app(app)
    migrate.init_app(app, db)

    # ---------------------------------------------------------
    # 📦 Models (CRÍTICO para Alembic)
    # ---------------------------------------------------------
    from app import models  # noqa
    from app import models_auth  # noqa
    from app import models_payment  # noqa
    from app import models_user  # noqa

    # ---------------------------------------------------------
    # 🧭 Blueprints
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # ❤️ Healthcheck
    # ---------------------------------------------------------
    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    return app
