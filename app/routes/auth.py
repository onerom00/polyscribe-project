# app/routes/auth.py
from __future__ import annotations

import secrets
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta

from flask import Blueprint, request, session, jsonify, current_app, redirect, url_for, render_template
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models_user import User

bp = Blueprint("auth", __name__)


# -------------------------
# Helpers
# -------------------------
def _bool_env(name: str, default: bool = False) -> bool:
    v = current_app.config.get(name, default)
    if isinstance(v, bool):
        return v
    return str(v).strip() == "1"


def _app_base_url() -> str:
    base = (current_app.config.get("APP_BASE_URL") or "").strip()
    return base.rstrip("/") if base else "https://www.getpolyscribe.com"


def _send_email(to_email: str, subject: str, html: str) -> None:
    host = current_app.config.get("SMTP_HOST", "smtp.gmail.com")
    port = int(current_app.config.get("SMTP_PORT", 587))
    user = (current_app.config.get("SMTP_USER") or "").strip()
    pwd = (current_app.config.get("SMTP_PASS") or "").strip()
    mail_from = (current_app.config.get("MAIL_FROM") or "PolyScribe <helppolyscribe@gmail.com>").strip()

    if not user or not pwd:
        raise RuntimeError("SMTP_USER/SMTP_PASS no configurados")

    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = to_email

    with smtplib.SMTP(host, port) as s:
        s.ehlo()
        s.starttls()
        s.login(user, pwd)
        s.sendmail(user, [to_email], msg.as_string())


def _serialize_user(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "display_name": u.display_name,
        "is_active": u.is_active,
        "is_verified": u.is_verified,
        "plan_tier": u.plan_tier,
        "minute_quota": u.minute_quota,
        "minutes_used": u.minutes_used,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }


def _require_verified() -> bool:
    return _bool_env("AUTH_REQUIRE_VERIFIED_EMAIL", True)


# -------------------------
# Pages
# -------------------------
@bp.get("/auth/login")
def login_page():
    return render_template("auth_login.html")


@bp.get("/auth/register")
def register_page():
    return render_template("auth_register.html")


# ✅ IMPORTANTE: tu ruta real actual es /dev-login
@bp.get("/dev-login")
def dev_login_alias():
    # En PROD, lo apagamos y mandamos a login real
    if _bool_env("DISABLE_DEVLOGIN", True):
        return redirect(url_for("auth.login_page"))

    # Si algún día lo reactivas en local, puedes renderizar tu template viejo aquí:
    # return render_template("dev_login.html", is_signup=True)
    return redirect(url_for("auth.login_page"))


@bp.get("/auth/verify")
def verify_email():
    token = (request.args.get("token") or "").strip()
    if not token:
        return render_template("auth_verify_result.html", ok=False, msg="Token inválido."), 400

    u = db.session.query(User).filter(User.verify_token == token).first()
    if not u:
        return render_template("auth_verify_result.html", ok=False, msg="Token inválido o ya usado."), 400

    if u.verify_expires_at and datetime.utcnow() > u.verify_expires_at:
        return render_template("auth_verify_result.html", ok=False, msg="Token vencido. Regístrate de nuevo."), 400

    u.is_verified = True
    u.verify_token = None
    u.verify_expires_at = None
    db.session.commit()

    return render_template("auth_verify_result.html", ok=True, msg="Correo verificado. Ya puedes iniciar sesión."), 200


# -------------------------
# API (JSON)
# -------------------------
@bp.get("/auth/ping")
def ping():
    return jsonify(ok=True, msg="pong")


@bp.get("/auth/me")
def me():
    uid = session.get("user_id") or session.get("uid")
    if not uid:
        return jsonify(authenticated=False), 200

    u = db.session.get(User, int(uid))
    if not u:
        return jsonify(authenticated=False), 200

    return jsonify(authenticated=True, user=_serialize_user(u)), 200


@bp.post("/auth/logout")
@bp.get("/auth/logout")
def logout():
    session.clear()
    return jsonify(ok=True), 200


@bp.post("/auth/register")
def register():
    data = request.get_json(silent=True) or request.form or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()
    display_name = (data.get("display_name") or "").strip()

    if not email or not password:
        return jsonify(ok=False, error="email y password requeridos"), 400
    if len(password) < 6:
        return jsonify(ok=False, error="La contraseña debe tener al menos 6 caracteres."), 400

    existing = db.session.query(User).filter(User.email == email).first()
    if existing:
        return jsonify(ok=False, error="Este correo ya está registrado."), 409

    token = secrets.token_urlsafe(32)
    u = User(
        email=email,
        display_name=display_name or email.split("@")[0],
        password_hash=generate_password_hash(password),
        is_active=True,
        is_verified=False,
        verify_token=token,
        verify_expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.session.add(u)
    db.session.commit()

    verify_url = f"{_app_base_url()}/auth/verify?token={token}"

    html = f"""
    <div style="font-family:system-ui,Segoe UI,Arial">
      <h2>Verifica tu correo en PolyScribe</h2>
      <p>Para activar tu cuenta, confirma tu correo haciendo clic aquí:</p>
      <p><a href="{verify_url}">{verify_url}</a></p>
      <p>Este enlace vence en 24 horas.</p>
    </div>
    """

    try:
        _send_email(email, "PolyScribe · Verifica tu correo", html)
    except Exception as e:
        current_app.logger.exception("SMTP send failed: %s", e)
        # Si falla el correo, dejamos la cuenta pero avisamos
        return jsonify(ok=False, error="No se pudo enviar el correo de verificación. Revisa SMTP en Render."), 500

    return jsonify(ok=True, msg="VERIFY_SENT"), 200


@bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or request.form or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify(ok=False, error="email y password requeridos"), 400

    u = db.session.query(User).filter(User.email == email).first()
    if not u:
        return jsonify(ok=False, error="Credenciales inválidas"), 401

    if not u.is_active:
        return jsonify(ok=False, error="Cuenta deshabilitada"), 403

    if _require_verified() and not u.is_verified:
        return jsonify(ok=False, error="EMAIL_NOT_VERIFIED"), 403

    if not u.password_hash or not check_password_hash(u.password_hash, password):
        return jsonify(ok=False, error="Credenciales inválidas"), 401

    u.last_login_at = datetime.utcnow()
    db.session.commit()

    session["user_id"] = int(u.id)
    session["uid"] = int(u.id)

    return jsonify(ok=True, user=_serialize_user(u)), 200
