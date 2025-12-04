# app/__init__.py
from __future__ import annotations

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Extensiones globales
db = SQLAlchemy()
migrate = Migrate()


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

    # Base de datos
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",          # en Render: sqlite:///polyscribe4.db (por ejemplo)
        "sqlite:///polyscribe4.db",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # -----------------------------------------------------------
    # CONFIG APP (URL base)
    # -----------------------------------------------------------
    app.config["APP_BASE_URL"] = os.getenv(
        "APP_BASE_URL",
        "https://polyscribe-project.onrender.com",
    )

    # -----------------------------------------------------------
    # CONFIG PAYPAL
    # -----------------------------------------------------------
    # sandbox / live
    app.config["PAYPAL_ENV"] = os.getenv("PAYPAL_ENV", "sandbox")

    # URL base API REST de PayPal
    app.config["PAYPAL_BASE_URL"] = os.getenv(
        "PAYPAL_BASE_URL",
        "https://api-m.sandbox.paypal.com",
    )

    # Credenciales (Render → Environment)
    app.config["PAYPAL_CLIENT_ID"] = os.getenv("PAYPAL_CLIENT_ID")
    app.config["PAYPAL_CLIENT_SECRET"] = os.getenv("PAYPAL_CLIENT_SECRET")

    # Moneda
    app.config["PAYPAL_CURRENCY"] = os.getenv("PAYPAL_CURRENCY", "USD")

    # ID del plan starter (por si lo necesitas más adelante)
    app.config["PAYPAL_PLAN_STARTER_ID"] = os.getenv(
        "PAYPAL_PLAN_STARTER_ID",
        "P-9W9394623R721322BNEW7GUY",
    )

    # Webhook ID (solo si verificas la firma)
    app.config["PAYPAL_WEBHOOK_ID"] = os.getenv("PAYPAL_WEBHOOK_ID")

    # Habilitar PayPal solo si hay credenciales
    app.config["PAYPAL_ENABLED"] = bool(
        app.config["PAYPAL_CLIENT_ID"] and app.config["PAYPAL_CLIENT_SECRET"]
    )

    # Minutos gratis
    app.config["FREE_TIER_MINUTES"] = int(os.getenv("FREE_TIER_MINUTES", "10"))

    # -----------------------------------------------------------
    # INICIALIZACIÓN DE EXTENSIONES
    # -----------------------------------------------------------
    db.init_app(app)
    migrate.init_app(app, db)

    # Importar modelos
    from app import models          # noqa: F401
    from app import models_payment  # noqa: F401

    # -----------------------------------------------------------
    # BLUEPRINTS
    # -----------------------------------------------------------
    from app.routes.pages import bp as pages_bp
    app.register_blueprint(pages_bp)

    from app.routes.jobs import bp as jobs_bp
    app.register_blueprint(jobs_bp)

    from app.routes.exports import bp as exports_bp
    app.register_blueprint(exports_bp)

    from app.routes.usage import bp as usage_bp
    app.register_blueprint(usage_bp)

    # PayPal: dos blueprints en el MISMO archivo
    #  - bp      → /paypal/...
    #  - api_bp  → /api/paypal/...
    from app.routes.paypal import bp as paypal_bp, api_bp as paypal_api_bp
    app.register_blueprint(paypal_bp)
    app.register_blueprint(paypal_api_bp)

    # -----------------------------------------------------------
    # HEALTHCHECK
    # -----------------------------------------------------------
    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    # Crear tablas si no existen
    with app.app_context():
        db.create_all()

    return app
