# app/__init__.py
from __future__ import annotations

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=os.getenv("FLASK_STATIC_FOLDER", "static"),
        template_folder=os.getenv("FLASK_TEMPLATES_FOLDER", "templates"),
    )

    # ──────────────────────────────────────────────────────────
    # CONFIG BÁSICA
    # ──────────────────────────────────────────────────────────
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///polyscribe.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # URL base de la app (para return_url / cancel_url de PayPal)
    app.config["APP_BASE_URL"] = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")

    # ──────────────────────────────────────────────────────────
    # CONFIG PAYPAL
    # ──────────────────────────────────────────────────────────
    app.config["PAYPAL_ENV"] = os.getenv("PAYPAL_ENV", "sandbox")
    app.config["PAYPAL_BASE_URL"] = os.getenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")
    app.config["PAYPAL_CLIENT_ID"] = os.getenv("PAYPAL_CLIENT_ID")
    app.config["PAYPAL_CLIENT_SECRET"] = os.getenv("PAYPAL_CLIENT_SECRET")
    app.config["PAYPAL_CURRENCY"] = os.getenv("PAYPAL_CURRENCY", "USD")
    app.config["PAYPAL_SKIP_VERIFY"] = os.getenv("PAYPAL_SKIP_VERIFY", "0") == "1"

    # PayPal se activa sólo si existen credenciales
    app.config["PAYPAL_ENABLED"] = bool(
        app.config["PAYPAL_CLIENT_ID"] and app.config["PAYPAL_CLIENT_SECRET"]
    )

    # Minutos nivel Free (por defecto 10, configurable por .env)
    app.config["FREE_TIER_MINUTES"] = int(
        os.getenv("FREE_TIER_MINUTES", "10")
    )

    # ──────────────────────────────────────────────────────────
    # INICIALIZAR EXTENSIONES
    # ──────────────────────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)

    # Importa modelos usando la misma instancia db
    from app import models  # noqa: F401
    try:
        from app import models_payment  # noqa: F401
    except Exception:
        pass

    # ──────────────────────────────────────────────────────────
    # REGISTRO DE BLUEPRINTS
    # ──────────────────────────────────────────────────────────

    # Páginas
    from app.routes.pages import bp as pages_bp
    if "pages" not in app.blueprints:
        app.register_blueprint(pages_bp)

    # Jobs
    try:
        from app.routes.jobs import bp as jobs_bp
        if "jobs" not in app.blueprints:
            app.register_blueprint(jobs_bp)
    except Exception:
        pass

    # Exports
    try:
        from app.routes.exports import bp as exports_bp
        if "exports" not in app.blueprints:
            app.register_blueprint(exports_bp)
    except Exception:
        pass

    # Usage (saldo de minutos)
    try:
        from app.routes.usage import bp as usage_bp
        if "usage" not in app.blueprints:
            app.register_blueprint(usage_bp)
    except Exception:
        pass

    # PayPal
    try:
        from app.routes.paypal import bp as paypal_bp
        if "paypal" not in app.blueprints:
            app.register_blueprint(paypal_bp)
    except Exception:
        pass

    # ──────────────────────────────────────────────────────────
    # HEALTH CHECK
    # ──────────────────────────────────────────────────────────
    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    # ──────────────────────────────────────────────────────────
    # CREAR TABLAS SI NO EXISTEN (SQLite / local)
    # ──────────────────────────────────────────────────────────
    with app.app_context():
        db.create_all()

    return app
