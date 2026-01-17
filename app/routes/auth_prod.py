# app/routes/auth_prod.py
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from flask import Blueprint, request, jsonify, session, current_app, render_template, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.extensions import db
from app.models_user import User
from app.services.mailer import send_email

bp = Blueprint("auth", __name__)

def _serializer() -> URLSafeTimedSerializer:
    secret = current_app.config.get("SECRET_KEY") or os.getenv("SECRET_KEY", "dev-secret")
    return URLSafeTimedSerializer(secret_key=secret, salt="polyscribe-email-verify")

def _make_token(user: User) -> str:
    s = _serializer()
    return s.dumps({"uid": user.id, "email": user.email})

def _load_token(token: str, max_age_seconds: int = 60 * 60 * 24) -> dict:
    s = _serializer()
    return s.loads(token, max_age=max_age_seconds)

def _app_base_url() -> str:
    return (current_app.config.get("APP_BASE_URL") or os.getenv("APP_BASE_URL") or "").rstrip("/")

def _send_verification_email(user: User) -> None:
    token = _make_token(user)
    verify_url = f"{_app_base_url()}/auth/verify/{token}"

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px">
      <h2>Verifica tu correo en PolyScribe</h2>
      <p>Hola{(" " + (user.display_name or "")) if user.display_name else ""},</p>
      <p>Para activar tu cuenta, confirma tu correo haciendo clic aquí:</p>
      <p><a href="{verify_url}" style="display:inline-block;padding:10px 14px;background:#0057d8;color:#fff;border-radius:10px;text-decoration:none">
        Verificar mi correo
      </a></p>
      <p style="color:#555;font-size:12px">Si no solicitaste esto, ignora este mensaje.</p>
    </div>
    """

    send_email(user.email, "Verifica tu correo · PolyScribe", html)

def _login_user(user: User) -> None:
    session["user_id"] = int(user.id)

def _current_user() -> Optional[User]:
    uid = session.get("user_id")
    if not uid:
        return None
    try:
        return db.session.get(User, int(uid))
    except Exception:
        return None

@bp.get("/auth/register")
def register_page():
    return render_template("auth_register.html")

@bp.post("/auth/register")
def register_post():
    data = request.form or request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    display_name = (data.get("name") or "").strip()

    if not email or not password:
        return jsonify(ok=False, error="Email y password son requeridos"), 400
    if len(password) < 8:
        return jsonify(ok=False, error="Password mínimo 8 caracteres"), 400

    existing = db.session.query(User).filter(User.email == email).first()
    if existing:
        return jsonify(ok=False, error="Este correo ya está registrado"), 409

    u = User(
        email=email,
        display_name=display_name or None,
        password_hash=generate_password_hash(password),
        is_active=True,
        is_verified=False,
        last_login_at=None,
    )
    db.session.add(u)
    db.session.commit()

    try:
        _send_verification_email(u)
    except Exception as e:
        current_app.logger.error("No se pudo enviar verificación: %s", e)

    return jsonify(ok=True, msg="Cuenta creada. Revisa tu correo para verificar."), 200

@bp.get("/auth/login")
def login_page():
    return render_template("auth_login.html")

@bp.post("/auth/login")
def login_post():
    data = request.form or request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify(ok=False, error="Email y password son requeridos"), 400

    u = db.session.query(User).filter(User.email == email).first()
    if not u or not check_password_hash(u.password_hash, password):
        return jsonify(ok=False, error="Credenciales inválidas"), 401

    if not u.is_active:
        return jsonify(ok=False, error="Cuenta desactivada"), 403

    u.last_login_at = datetime.utcnow()
    db.session.commit()

    _login_user(u)
    return jsonify(ok=True, verified=bool(u.is_verified)), 200

@bp.get("/auth/verify/<token>")
def verify_email(token: str):
    try:
        payload = _load_token(token, max_age_seconds=60 * 60 * 24)  # 24h
        uid = int(payload["uid"])
        email = str(payload["email"]).strip().lower()
    except SignatureExpired:
        return render_template("auth_check_inbox.html", msg="El enlace expiró. Solicita uno nuevo."), 400
    except BadSignature:
        return render_template("auth_check_inbox.html", msg="Enlace inválido."), 400
    except Exception:
        return render_template("auth_check_inbox.html", msg="Enlace inválido."), 400

    u = db.session.get(User, uid)
    if not u or u.email != email:
        return render_template("auth_check_inbox.html", msg="Usuario no válido."), 400

    if not u.is_verified:
        u.is_verified = True
        db.session.commit()

    # opcional: auto-login tras verificar
    _login_user(u)
    return redirect(url_for("pages.index"))

@bp.post("/auth/resend-verification")
def resend_verification():
    data = request.form or request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify(ok=False, error="Email requerido"), 400

    u = db.session.query(User).filter(User.email == email).first()
    if not u:
        return jsonify(ok=True, msg="Si existe, se envió el correo."), 200

    if u.is_verified:
        return jsonify(ok=True, msg="Tu correo ya está verificado."), 200

    try:
        _send_verification_email(u)
    except Exception as e:
        current_app.logger.error("resend verification failed: %s", e)

    return jsonify(ok=True, msg="Revisa tu correo. Te reenviamos el enlace."), 200

@bp.get("/auth/me")
def me():
    u = _current_user()
    if not u:
        return jsonify(authenticated=False), 200
    return jsonify(
        authenticated=True,
        user={
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name,
            "is_verified": bool(u.is_verified),
            "plan_tier": u.plan_tier,
        },
    ), 200

@bp.route("/auth/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    return jsonify(ok=True), 200
