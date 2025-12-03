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

    # -----------------------------------------------------------
    # CONFIG GENERAL
    # -----------------------------------------------------------
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")

    # Base de datos
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///polyscribe.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # -----------------------------------------------------------
    # CONFIG APP
    # -----------------------------------------------------------
    app.config["APP_BASE_URL"] = os.getenv(
        "APP_BASE_URL",
        "https://polyscribe-project.onrender.com"
    )

    # -----------------------------------------------------------
    # CONFIG PAYPAL
    # -----------------------------------------------------------
    app.config["PAYPAL_ENV"] = os.getenv("PAYPAL_ENV", "sandbox")
    app.config["PAYPAL_BASE_URL"] = os.getenv(
        "PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com"
    )
    app.config["PAYPAL_CLIENT_ID"] = os.getenv("PAYPAL_CLIENT_ID")
    app.config["PAYPAL_CLIENT_SECRET"] = os.getenv("PAYPAL_CLIENT_SECRET")
    app.config["PAYPAL_CURRENCY"] = "USD"

    # PLANES
    app.config["PAYPAL_PLAN_STARTER_ID"] = os.getenv("PAYPAL_PLAN_STARTER_ID")

    # WEBHOOK ID (sandbox)
    app.config["PAYPAL_WEBHOOK_ID"] = os.getenv("PAYPAL_WEBHOOK_ID")

    # PayPal habilitado si existen credenciales
    app.config["PAYPAL_ENABLED"] = (
        bool(app.config["PAYPAL_CLIENT_ID"])
        and bool(app.config["PAYPAL_CLIENT_SECRET"])
    )

    # Free tier
    app.config["FREE_TIER_MINUTES"] = int(os.getenv("FREE_TIER_MINUTES", "10"))

    # -----------------------------------------------------------
    # INICIALIZACIÓN DE EXTENSIONES
    # -----------------------------------------------------------
    db.init_app(app)
    migrate.init_app(app, db)

    # -----------------------------------------------------------
    # MODELOS (IMPORTANTE QUE SE IMPORTEN ANTES DE CREAR TABLAS)
    # -----------------------------------------------------------
    from app import models
    from app import models_payment

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

    from app.routes.paypal import bp as paypal_bp
    app.register_blueprint(paypal_bp)

    # -----------------------------------------------------------
    # HEALTHCHECK
    # -----------------------------------------------------------
    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    # -----------------------------------------------------------
    # CREAR TABLAS (Solo SQLite local — Ok también para Render)
    # -----------------------------------------------------------
    with app.app_context():
        db.create_all()

    return app
