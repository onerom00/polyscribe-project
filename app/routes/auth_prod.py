# app/routes/auth_prod.py
from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.extensions import db
from app.models_user import User

bp = Blueprint("auth", __name__)

def _serializer() -> URLSafeTimedSerializer:
    secret = current_app.config["SECRET_KEY"]
    return URLSafeTimedSerializer(secret, salt="email-verify")

def _send_email(to_email: str, subject: str, html: str) -> None:
    host = current_app.config.get("SMTP_HOST")
    port = int(current_app.config.get("SMTP_PORT", 587))
    user = current_app.config.get("SMTP_USER")
    pwd = current_app.config.get("SMTP_PASS")
    mail_from = current_app.config.get("MAIL_FROM") or user

    if not host or not user or not pwd or not mail_from:
        raise RuntimeError("SMTP no configurado (SMTP_HOST/SMTP_USER/SMTP_PASS/MAIL_FROM)")

    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = to_email

    with smtplib.SMTP(host, port) as s:
        s.ehlo()
        s.starttls()
        s.login(user, pwd)
        s.sendmail(mail_from, [to_email], msg.as_string())

def _app_base() -> str:
    return (current_app.config.get("APP_BASE_URL") or "").rstrip("/")

@bp.get("/auth/me")
def me():
    uid = session.get("user_id")
    if not uid:
        return jsonify(authenticated=False), 200
    u = db.session.get(User, int(uid))
    if not u:
        session.clear()
        return jsonify(authenticated=False), 200
    return jsonify(authenticated=True, user={
        "id": u.id,
        "email": u.email,
        "display_name": u.display_name,
        "is_verified": bool(u.is_verified),
        "plan_tier": u.plan_tier,
    }), 200

@bp.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    display_name = (data.get("display_name") or "").strip() or None

    if not email or not password:
        return jsonify(ok=False, error="email y password requeridos"), 400

    exists = db.session.query(User).filter(User.email == email).first()
    if exists:
        return jsonify(ok=False, error="EMAIL_ALREADY_EXISTS"), 409

    u = User(
        email=email,
        display_name=display_name,
        password_hash=generate_password_hash(password),
        is_active=True,
        is_verified=False,
        plan_tier="free",
        minute_quota=0,
        minutes_used=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.session.add(u)
    db.session.commit()

    token = _serializer().dumps({"uid": u.id, "email": u.email})
    verify_url = f"{_app_base()}{url_for('auth.verify_email', token=token)}"

    html = f"""
    <div style="font-family:Arial,sans-serif">
      <h2>Verifica tu correo en PolyScribe</h2>
      <p>Haz clic para verificar tu cuenta:</p>
      <p><a href="{verify_url}">Verificar mi correo</a></p>
      <p>Si no fuiste tú, ignora este mensaje.</p>
    </div>
    """

    try:
        _send_email(u.email, "PolyScribe — Verificación de correo", html)
    except Exception as e:
        current_app.logger.error("No se pudo enviar email de verificación: %s", e)
        # el usuario queda creado igual (pero no verificado)
        return jsonify(ok=True, user_id=u.id, email=u.email, verify_sent=False), 200

    return jsonify(ok=True, user_id=u.id, email=u.email, verify_sent=True), 200

@bp.get("/auth/verify/<token>")
def verify_email(token: str):
    ttl = int(current_app.config.get("VERIFY_TOKEN_TTL_SECONDS", 86400))
    try:
        payload = _serializer().loads(token, max_age=ttl)
    except SignatureExpired:
        return "Link expirado. Solicita uno nuevo.", 400
    except BadSignature:
        return "Token inválido.", 400

    uid = int(payload.get("uid"))
    u = db.session.get(User, uid)
    if not u:
        return "Usuario no existe.", 404

    u.is_verified = True
    db.session.commit()

    # auto-login tras verificar
    session["user_id"] = int(u.id)
    session["uid"] = int(u.id)

    return "✅ Correo verificado. Ya puedes usar PolyScribe. Vuelve a la pestaña y refresca.", 200

@bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify(ok=False, error="email y password requeridos"), 400

    u = db.session.query(User).filter(User.email == email).first()
    if not u:
        return jsonify(ok=False, error="USER_NOT_FOUND"), 401

    if not u.is_active:
        return jsonify(ok=False, error="USER_DISABLED"), 403

    if not check_password_hash(u.password_hash, password):
        return jsonify(ok=False, error="BAD_CREDENTIALS"), 401

    if current_app.config.get("AUTH_REQUIRE_VERIFIED_EMAIL", True) and not u.is_verified:
        return jsonify(ok=False, error="EMAIL_NOT_VERIFIED"), 403

    u.last_login_at = datetime.utcnow()
    db.session.commit()

    session["user_id"] = int(u.id)
    session["uid"] = int(u.id)

    return jsonify(ok=True, user={"id": u.id, "email": u.email, "is_verified": bool(u.is_verified)}), 200

@bp.post("/auth/logout")
def logout():
    session.clear()
    return jsonify(ok=True), 200
