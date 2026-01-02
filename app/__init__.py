# app/__init__.py
from __future__ import annotations

import os
from flask import Flask

# ✅ Usar SIEMPRE el mismo db/migrate desde app/extensions.py
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
    # CONFIG APP (URL base)
    # -----------------------------------------------------------
    app.config["APP_BASE_URL"] = os.getenv(
        "APP_BASE_URL",
        "https://polyscribe-project.onrender.com",
    )

    # -----------------------------------------------------------
    # CONFIG PAYPAL
    # -----------------------------------------------------------
    app.config["PAYPAL_ENV"] = os.getenv("PAYPAL_ENV", "sandbox")
    app.config["PAYPAL_BASE_URL"] = os.getenv(
        "PAYPAL_BASE_URL",
        "https://api-m.sandbox.paypal.com",
    )

    app.config["PAYPAL_CLIENT_ID"] = os.getenv("PAYPAL_CLIENT_ID")
    app.config["PAYPAL_CLIENT_SECRET"] = os.getenv("PAYPAL_CLIENT_SECRET")
    app.config["PAYPAL_CURRENCY"] = os.getenv("PAYPAL_CURRENCY", "USD")

    app.config["PAYPAL_PLAN_STARTER_ID"] = os.getenv(
        "PAYPAL_PLAN_STARTER_ID",
        "P-9W9394623R721322BNEW7GUY",
    )

    app.config["PAYPAL_WEBHOOK_ID"] = os.getenv("PAYPAL_WEBHOOK_ID")

    app.config["PAYPAL_ENABLED"] = bool(
        app.config["PAYPAL_CLIENT_ID"] and app.config["PAYPAL_CLIENT_SECRET"]
    )

    app.config["FREE_TIER_MINUTES"] = int(os.getenv("FREE_TIER_MINUTES", "10"))

    # -----------------------------------------------------------
    # INICIALIZACIÓN DE EXTENSIONES
    # -----------------------------------------------------------
    db.init_app(app)
    migrate.init_app(app, db)

    # -----------------------------------------------------------
    # IMPORTAR MODELOS (para que Alembic/SQLAlchemy los detecte)
    # -----------------------------------------------------------
    # OJO: evita tener 2 modelos User distintos en 2 archivos distintos.
    from app import models  # noqa: F401
    from app import models_payment  # noqa: F401
    from app import models_user  # noqa: F401

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

    from app.routes.paypal import bp as paypal_bp, api_bp as paypal_api_bp
    app.register_blueprint(paypal_bp)
    app.register_blueprint(paypal_api_bp)

    # ✅ Auth blueprint (si lo estás usando)
    try:
        from app.routes.auth import bp as auth_bp
        app.register_blueprint(auth_bp)
    except Exception:
        # si aún no lo tienes listo, no tumba el deploy
        pass

    # ❌ IMPORTANTE: NO registres pricing_page.py si ya tienes /pricing en pages.py
    # (dos rutas iguales /pricing te pueden causar problemas)
    # from app.routes.pricing_page import bp as pricing_page_bp
    # app.register_blueprint(pricing_page_bp)

    # -----------------------------------------------------------
    # HEALTHCHECK
    # -----------------------------------------------------------
    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    # Crear tablas (solo SQLite/dev). En prod ideal usar migrations.
    with app.app_context():
        db.create_all()

    return app
