# app/routes/auth.py
from __future__ import annotations

from datetime import datetime
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from flask import (
    Blueprint, request, session, jsonify, current_app,
    redirect, url_for, render_template, flash
)
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models_user import User
from app.utils_mail import send_email

bp = Blueprint("auth", __name__)


# -------------------------
# Helpers
# -------------------------
def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def _make_verify_token(email: str) -> str:
    return _serializer().dumps(email, salt="email-verify")


def _read_verify_token(token: str, max_age_seconds: int) -> str:
    return _serializer().loads(token, salt="email-verify", max_age=max_age_seconds)


def _base_url() -> str:
    return (current_app.config.get("APP_BASE_URL") or "").rstrip("/")


def _login_user(u: User) -> None:
    session["user_id"] = int(u.id)
    session["uid"] = int(u.id)


def _logout_user() -> None:
    session.clear()


def _serialize_user(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "display_name": u.display_name,
        "is_active": bool(u.is_active),
        "is_verified": bool(u.is_verified),
        "plan_tier": getattr(u, "plan_tier", "free"),
        "minute_quota": getattr(u, "minute_quota", 0),
        "minutes_used": getattr(u, "minutes_used", 0),
        "last_login_at": getattr(u, "last_login_at", None),
    }


def _send_verification_email(email: str) -> None:
    token = _make_verify_token(email)
    link = f"{_base_url()}/auth/verify?token={token}"

    subject = "PolyScribe – Verifica tu correo"
    text = (
        "Hola,\n\n"
        "Para activar tu cuenta en PolyScribe, verifica tu correo haciendo click en este enlace:\n\n"
        f"{link}\n\n"
        "Si no solicitaste esta cuenta, ignora este mensaje.\n"
    )
    html = f"""
    <div style="font-family:system-ui,Segoe UI,Arial;line-height:1.4">
      <h2>Verifica tu correo en PolyScribe</h2>
      <p>Para activar tu cuenta, haz click aquí:</p>
      <p><a href="{link}" style="display:inline-block;padding:10px 14px;background:#0057d8;color:#fff;border-radius:999px;text-decoration:none">
        Verificar correo
      </a></p>
      <p style="color:#555">Si el botón no funciona, copia y pega este enlace:</p>
      <p style="color:#111">{link}</p>
      <hr/>
      <p style="color:#777;font-size:12px">Si no solicitaste esta cuenta, ignora este mensaje.</p>
    </div>
    """
    send_email(email, subject, text, html)


# -------------------------
# Diag / Ping
# -------------------------
@bp.route("/auth/ping", methods=["GET"])
def ping():
    return jsonify(ok=True, msg="pong")


@bp.route("/auth/diag", methods=["GET"])
def diag():
    return jsonify(ok=True, diag={
        "has_secret_key": bool(current_app.secret_key),
        "session_cookie_secure": bool(current_app.config.get("SESSION_COOKIE_SECURE")),
        "auth_require_verified": bool(current_app.config.get("AUTH_REQUIRE_VERIFIED_EMAIL")),
    })


# -------------------------
# Views (HTML)
# -------------------------
@bp.get("/auth/register")
def register_page():
    return render_template("auth_register.html")


@bp.get("/auth/login")
def login_page():
    return render_template("auth_login.html")


@bp.get("/auth/verify-sent")
def verify_sent_page():
    return render_template("auth_verify_sent.html")


@bp.get("/auth/verified")
def verified_ok_page():
    return render_template("auth_verified_ok.html")


@bp.get("/auth/verify-failed")
def verified_failed_page():
    msg = request.args.get("msg") or "No se pudo verificar el correo."
    return render_template("auth_verify_failed.html", msg=msg)


# -------------------------
# API/POST register/login/logout
# -------------------------
@bp.route("/auth/register", methods=["POST"])
def register():
    # soporta form o JSON
    data = request.get_json(silent=True) or request.form or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    display_name = (data.get("display_name") or "").strip()

    if not email or not password:
        return jsonify(ok=False, error="email y password requeridos"), 400
    if len(password) < 8:
        return jsonify(ok=False, error="La contraseña debe tener al menos 8 caracteres."), 400

    exists = db.session.query(User).filter(User.email == email).first()
    if exists:
        return jsonify(ok=False, error="Ese correo ya está registrado."), 409

    u = User(
        email=email,
        display_name=display_name or email.split("@")[0],
        password_hash=generate_password_hash(password),
        is_active=True,
        is_verified=False,
        plan_tier="free",
        minute_quota=int(current_app.config.get("FREE_TIER_MINUTES", 10)),
        minutes_used=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.session.add(u)
    db.session.commit()

    # enviar verificación (si SMTP está configurado)
    try:
        _send_verification_email(email)
    except Exception as e:
        current_app.logger.error("No se pudo enviar email verificación: %s", e)
        # No rompemos el registro: el usuario puede pedir resend
        return jsonify(ok=True, user=_serialize_user(u), warning="NO_EMAIL_SENT"), 200

    return jsonify(ok=True, user=_serialize_user(u)), 200


@bp.route("/auth/resend", methods=["POST"])
def resend_verification():
    data = request.get_json(silent=True) or request.form or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify(ok=False, error="email requerido"), 400

    u = db.session.query(User).filter(User.email == email).first()
    if not u:
        return jsonify(ok=False, error="Usuario no encontrado"), 404
    if u.is_verified:
        return jsonify(ok=True, msg="Ya estás verificado."), 200

    try:
        _send_verification_email(email)
        return jsonify(ok=True, msg="Email reenviado."), 200
    except Exception as e:
        current_app.logger.error("resend failed: %s", e)
        return jsonify(ok=False, error="No se pudo reenviar el email."), 500


@bp.route("/auth/verify", methods=["GET"])
def verify_email():
    token = request.args.get("token") or ""
    if not token:
        return redirect(url_for("auth.verified_failed_page", msg="Falta token."))

    ttl = int(current_app.config.get("EMAIL_VERIFY_TTL_SECONDS", 86400))

    try:
        email = _read_verify_token(token, ttl)
    except SignatureExpired:
        return redirect(url_for("auth.verified_failed_page", msg="Token expirado. Reenvía verificación."))
    except BadSignature:
        return redirect(url_for("auth.verified_failed_page", msg="Token inválido."))

    u = db.session.query(User).filter(User.email == email).first()
    if not u:
        return redirect(url_for("auth.verified_failed_page", msg="Usuario no encontrado."))

    if not u.is_verified:
        u.is_verified = True
        u.updated_at = datetime.utcnow()
        db.session.commit()

    return redirect(url_for("auth.verified_ok_page"))


@bp.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or request.form or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify(ok=False, error="email y password requeridos"), 400

    u = db.session.query(User).filter(User.email == email).first()
    if not u:
        return jsonify(ok=False, error="Credenciales inválidas"), 401
    if not u.is_active:
        return jsonify(ok=False, error="Cuenta desactivada"), 403

    if not u.password_hash or not check_password_hash(u.password_hash, password):
        return jsonify(ok=False, error="Credenciales inválidas"), 401

    # Si en PROD requieres verificado
    if current_app.config.get("AUTH_REQUIRE_VERIFIED_EMAIL", False) and not u.is_verified:
        return jsonify(ok=False, error="EMAIL_NOT_VERIFIED"), 403

    u.last_login_at = datetime.utcnow()
    db.session.commit()

    _login_user(u)
    return jsonify(ok=True, user=_serialize_user(u)), 200


@bp.route("/auth/me", methods=["GET"])
def me():
    uid = session.get("user_id") or session.get("uid")
    if not uid:
        return jsonify(authenticated=False), 200
    u = db.session.get(User, int(uid))
    if not u:
        return jsonify(authenticated=False), 200
    return jsonify(authenticated=True, user=_serialize_user(u)), 200


@bp.route("/auth/logout", methods=["POST", "GET"])
def logout():
    _logout_user()
    return jsonify(ok=True), 200


# -------------------------
# (PROD) Bloquear DEV routes
# -------------------------
@bp.get("/devlogin")
@bp.get("/dev-login")
def devlogin_block():
    # En producción no se usa.
    return redirect(url_for("auth.login_page"))
