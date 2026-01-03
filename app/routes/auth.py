# app/routes/auth.py
from __future__ import annotations

from datetime import datetime
from urllib.parse import urljoin

from flask import Blueprint, request, session, jsonify, current_app, redirect, url_for, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.extensions import db
from app.models_user import User

bp = Blueprint("auth", __name__)


def _ser() -> URLSafeTimedSerializer:
    secret = current_app.config.get("SECRET_KEY") or "dev-secret"
    return URLSafeTimedSerializer(secret_key=secret, salt=current_app.config.get("EMAIL_VERIFY_SALT", "polyscribe-email-verify"))


def _send_email(to_email: str, subject: str, body: str) -> bool:
    """
    En PROD usa SMTP. En DEV puedes dejar MAIL_ENABLED=0 y solo loguea.
    """
    if not current_app.config.get("MAIL_ENABLED"):
        current_app.logger.warning("MAIL_DISABLED: subject=%s to=%s body=%s", subject, to_email, body)
        return False

    import smtplib
    from email.mime.text import MIMEText

    host = current_app.config.get("SMTP_HOST")
    port = int(current_app.config.get("SMTP_PORT", 587))
    user = current_app.config.get("SMTP_USER")
    pw = current_app.config.get("SMTP_PASS")
    mail_from = current_app.config.get("MAIL_FROM")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = to_email

    try:
        with smtplib.SMTP(host, port, timeout=20) as s:
            s.ehlo()
            s.starttls()
            s.login(user, pw)
            s.sendmail(mail_from, [to_email], msg.as_string())
        return True
    except Exception as e:
        current_app.logger.exception("SMTP_SEND_FAILED: %s", e)
        return False


def _verification_link(email: str) -> str:
    token = _ser().dumps({"email": email})
    base = current_app.config.get("APP_BASE_URL", "").rstrip("/") + "/"
    return urljoin(base, "auth/verify?token=" + token)


def _serialize_user(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "display_name": u.display_name,
        "is_active": u.is_active,
        "is_verified": u.is_verified,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "last_login_at": u.last_login_at.isoformat() if getattr(u, "last_login_at", None) else None,
    }


@bp.get("/auth/ping")
def ping():
    return jsonify(ok=True, msg="pong")


@bp.get("/auth/login")
def login_page():
    # si no tienes el template, puedes redirigir a dev_login
    try:
        return render_template("auth_login.html")
    except Exception:
        return redirect(url_for("pages.dev_login"))


@bp.get("/auth/register")
def register_page():
    try:
        return render_template("auth_register.html")
    except Exception:
        return redirect(url_for("pages.dev_login"))


@bp.post("/auth/register")
def register_api():
    data = request.get_json(silent=True) or request.form or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    display_name = (data.get("display_name") or "").strip() or None

    if not email or not password:
        return jsonify(ok=False, error="email y password requeridos"), 400
    if len(password) < 8:
        return jsonify(ok=False, error="Password mínimo 8 caracteres"), 400

    exists = db.session.query(User).filter(User.email == email).first()
    if exists:
        return jsonify(ok=False, error="Este correo ya está registrado"), 409

    u = User(
        email=email,
        display_name=display_name,
        password_hash=generate_password_hash(password),
        is_active=True,
        is_verified=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.session.add(u)
    db.session.commit()

    link = _verification_link(email)
    body = (
        "Hola,\n\n"
        "Gracias por registrarte en PolyScribe.\n"
        "Para activar tu cuenta, verifica tu correo aquí:\n\n"
        f"{link}\n\n"
        "Si no fuiste tú, ignora este correo.\n"
    )
    _send_email(email, "Verifica tu cuenta en PolyScribe", body)

    return jsonify(ok=True, message="Cuenta creada. Revisa tu email para verificar.", user=_serialize_user(u)), 201


@bp.get("/auth/verify")
def verify_email():
    token = request.args.get("token") or ""
    if not token:
        return "Token faltante", 400

    max_age = int(current_app.config.get("EMAIL_VERIFY_MAX_AGE", 86400))

    try:
        data = _ser().loads(token, max_age=max_age)
        email = (data.get("email") or "").strip().lower()
    except SignatureExpired:
        return "Token expirado. Solicita uno nuevo.", 400
    except BadSignature:
        return "Token inválido.", 400

    u = db.session.query(User).filter(User.email == email).first()
    if not u:
        return "Usuario no encontrado.", 404

    if not u.is_verified:
        u.is_verified = True
        u.updated_at = datetime.utcnow()
        db.session.commit()

    # inicia sesión automáticamente
    session["uid"] = int(u.id)
    session["user_id"] = int(u.id)

    # redirige al home ya autenticado
    return redirect(url_for("pages.index"))


@bp.post("/auth/resend-verify")
def resend_verify():
    data = request.get_json(silent=True) or request.form or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify(ok=False, error="email requerido"), 400

    u = db.session.query(User).filter(User.email == email).first()
    if not u:
        return jsonify(ok=False, error="Usuario no encontrado"), 404
    if u.is_verified:
        return jsonify(ok=True, message="Ya estaba verificado."), 200

    link = _verification_link(email)
    body = f"Verifica tu cuenta aquí:\n\n{link}\n"
    _send_email(email, "Verifica tu cuenta en PolyScribe", body)
    return jsonify(ok=True, message="Correo reenviado."), 200


@bp.post("/auth/login")
def login_api():
    data = request.get_json(silent=True) or request.form or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify(ok=False, error="email y password requeridos"), 400

    u = db.session.query(User).filter(User.email == email).first()
    if not u:
        return jsonify(ok=False, error="Usuario no encontrado"), 401

    if not u.is_active:
        return jsonify(ok=False, error="Usuario desactivado"), 403

    if not check_password_hash(u.password_hash, password):
        return jsonify(ok=False, error="Credenciales inválidas"), 401

    # si quieres forzar verificación antes de login:
    if not u.is_verified:
        return jsonify(ok=False, error="Debes verificar tu correo antes de entrar."), 403

    # login ok
    session["uid"] = int(u.id)
    session["user_id"] = int(u.id)

    try:
        u.last_login_at = datetime.utcnow()  # type: ignore[attr-defined]
        db.session.commit()
    except Exception:
        db.session.rollback()

    return jsonify(ok=True, user=_serialize_user(u)), 200


@bp.get("/auth/me")
def me():
    uid = session.get("uid") or session.get("user_id")
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
