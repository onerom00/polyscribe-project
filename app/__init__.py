# app/__init__.py
from __future__ import annotations

import os
from flask import Flask, jsonify, session, g, request, redirect, send_from_directory

from app.extensions import db, migrate


def _fix_database_url(url: str) -> str:
    """
    Render a veces entrega DATABASE_URL con:
    - esquema 'postgres://' (legacy)
    - espacios / saltos de línea invisibles al final
    SQLAlchemy prefiere 'postgresql://'
    """
    url = (url or "").strip()

    # Caso típico de error: alguien pegó texto tipo "Internal Database URL"
    if url.lower().startswith("internal database url"):
        raise ValueError(
            "DATABASE_URL inválida: parece contener el texto 'Internal Database URL'. "
            "Debes pegar la URL completa real (postgresql://...)."
        )

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

    # DB
    raw_db_url = os.getenv("DATABASE_URL", "sqlite:///polyscribe.db")
    raw_db_url = (raw_db_url or "").strip()
    app.config["SQLALCHEMY_DATABASE_URI"] = _fix_database_url(raw_db_url)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Base URL
    app.config["APP_BASE_URL"] = os.getenv("APP_BASE_URL", "https://www.getpolyscribe.com").strip()

    # ✅ Cookies de sesión robustas (HTTPS + cross-subdomain)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    app.config["SESSION_COOKIE_SECURE"] = (
        os.getenv("SESSION_COOKIE_SECURE", "1") == "1"
        if app.config["APP_BASE_URL"].startswith("https://")
        else False
    )

    # ✅ permite que la cookie aplique tanto a www.getpolyscribe.com como getpolyscribe.com
    app.config["SESSION_COOKIE_DOMAIN"] = os.getenv("SESSION_COOKIE_DOMAIN", ".getpolyscribe.com")

    # Auth flags
    app.config["AUTH_REQUIRE_VERIFIED_EMAIL"] = os.getenv("AUTH_REQUIRE_VERIFIED_EMAIL", "1") == "1"
    app.config["DISABLE_DEVLOGIN"] = os.getenv("DISABLE_DEVLOGIN", "1") == "1"

    # SMTP
    app.config["SMTP_HOST"] = os.getenv("SMTP_HOST", "smtp.gmail.com")
    app.config["SMTP_PORT"] = int(os.getenv("SMTP_PORT", "587"))
    app.config["SMTP_USER"] = os.getenv("SMTP_USER", "")
    app.config["SMTP_PASS"] = os.getenv("SMTP_PASS", "")
    app.config["MAIL_FROM"] = os.getenv("MAIL_FROM", "PolyScribe <helppolyscribe@gmail.com>")

    # PayPal
    app.config["PAYPAL_ENV"] = os.getenv("PAYPAL_ENV", "sandbox")
    app.config["PAYPAL_BASE_URL"] = os.getenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")
    app.config["PAYPAL_CLIENT_ID"] = os.getenv("PAYPAL_CLIENT_ID")
    app.config["PAYPAL_CLIENT_SECRET"] = os.getenv("PAYPAL_CLIENT_SECRET")
    app.config["PAYPAL_CURRENCY"] = os.getenv("PAYPAL_CURRENCY", "USD")
    app.config["PAYPAL_PLAN_STARTER_ID"] = os.getenv("PAYPAL_PLAN_STARTER_ID", "P-9W9394623R721322BNEW7GUY")
    app.config["PAYPAL_WEBHOOK_ID"] = os.getenv("PAYPAL_WEBHOOK_ID")
    app.config["PAYPAL_ENABLED"] = bool(app.config["PAYPAL_CLIENT_ID"] and app.config["PAYPAL_CLIENT_SECRET"])

    app.config["FREE_TIER_MINUTES"] = int(os.getenv("FREE_TIER_MINUTES", "10"))

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Import models (alembic)
    from app import models  # noqa: F401
    from app import models_auth  # noqa: F401
    from app import models_payment  # noqa: F401
    try:
        from app import models_user  # noqa: F401
    except Exception:
        pass

    # ============================================================
    # ✅ Canonical domain (evita login perdido por www vs no-www)
    # ============================================================
    CANONICAL_HOST = os.getenv("CANONICAL_HOST", "www.getpolyscribe.com").strip().lower()

    @app.before_request
    def _force_canonical_host():
        if os.getenv("DISABLE_CANONICAL_REDIRECT", "0") == "1":
            return None

        host = (request.host or "").split(":")[0].lower()
        if not host:
            return None

        if request.path.startswith("/healthz"):
            return None

        if host == CANONICAL_HOST:
            return None

        if host in ("getpolyscribe.com", "www.getpolyscribe.com"):
            scheme = "https" if app.config["APP_BASE_URL"].startswith("https://") else request.scheme
            new_url = f"{scheme}://{CANONICAL_HOST}{request.full_path}"
            if new_url.endswith("?"):
                new_url = new_url[:-1]
            return redirect(new_url, code=301)

        return None

    # ============================================================
    # ✅ AUTH BRIDGE (sesión -> g.user_id -> templates)
    # ============================================================

    def _get_session_user_id() -> str | None:
        uid = session.get("user_id") or session.get("uid")
        if not uid:
            return None
        uid = str(uid).strip()
        if not uid or uid.lower() == "guest":
            return None
        return uid

    @app.before_request
    def _load_user_into_g():
        g.user_id = _get_session_user_id()

    @app.context_processor
    def _inject_user_into_templates():
        return {
            "user_id": getattr(g, "user_id", None) or "",
            "paypal_enabled": bool(app.config.get("PAYPAL_ENABLED", False)),
        }

    # ============================================================
    # ✅ SEO: servir robots.txt y sitemap.xml en la raíz
    # ============================================================

    @app.get("/robots.txt")
    def robots_txt():
        return send_from_directory(app.static_folder, "robots.txt")

    @app.get("/sitemap.xml")
    def sitemap_xml():
        return send_from_directory(app.static_folder, "sitemap.xml")

    # Extra: evita indexación del dev-login aunque alguien lo encuentre
    @app.after_request
    def _noindex_devlogin(resp):
        try:
            if (request.path or "").startswith("/dev-login"):
                resp.headers["X-Robots-Tag"] = "noindex, nofollow"
        except Exception:
            pass
        return resp

    # ============================================================

    # Blueprints
    from app.routes.pages import bp as pages_bp
    app.register_blueprint(pages_bp)

    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    # ✅ /api/auth/me
    from app.routes.auth_api import bp as auth_api_bp
    app.register_blueprint(auth_api_bp)

    from app.routes.jobs import bp as jobs_bp
    app.register_blueprint(jobs_bp)

    from app.routes.exports import bp as exports_bp
    app.register_blueprint(exports_bp)

    from app.routes.usage import bp as usage_bp
    app.register_blueprint(usage_bp)

    from app.routes.history import bp as history_bp
    app.register_blueprint(history_bp)

    from app.routes.paypal import bp as paypal_bp, api_bp as paypal_api_bp
    app.register_blueprint(paypal_bp)
    app.register_blueprint(paypal_api_bp)

    from app.routes.pricing_page import bp as pricing_page_bp
    app.register_blueprint(pricing_page_bp)

    # ✅ /account
    from app.routes.account_page import bp as account_page_bp
    app.register_blueprint(account_page_bp)

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    return app
