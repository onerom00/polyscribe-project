# app/routes/auth.py
from __future__ import annotations

import os
import secrets
import datetime as dt
from urllib.parse import urljoin

from flask import (
    Blueprint, request, render_template, redirect, url_for,
    flash, session, current_app
)
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models_user import User
from app.models_auth import EmailVerificationToken, PasswordResetToken

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _base_url() -> str:
    base = (current_app.config.get("APP_BASE_URL") or os.getenv("APP_BASE_URL") or "").strip()
    return base.rstrip("/") + "/"


def _send_email(to_email: str, subject: str, html_body: str) -> None:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    host = current_app.config.get("SMTP_HOST", os.getenv("SMTP_HOST", "smtp.gmail.com"))
    port = int(current_app.config.get("SMTP_PORT", os.getenv("SMTP_PORT", "587")))
    user = current_app.config.get("SMTP_USER", os.getenv("SMTP_USER", ""))
    pw = current_app.config.get("SMTP_PASS", os.getenv("SMTP_PASS", ""))
    from_addr = current_app.config.get("MAIL_FROM", os.getenv("MAIL_FROM", f"PolyScribe <{user}>"))

    if not user or not pw:
        current_app.logger.warning("SMTP not configured. Skipping email to=%s subject=%s", to_email, subject)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(host, port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(user, pw)
        smtp.sendmail(from_addr, [to_email], msg.as_string())


def _login_user(user: User) -> None:
    session["user_id"] = str(user.id)


def _logout_user() -> None:
    session.pop("user_id", None)


def current_user_id() -> int | None:
    v = session.get("user_id")
    if not v:
        return None
    try:
        return int(v)
    except Exception:
        return None


@bp.get("/register")
def register_page():
    return render_template("auth/register.html")


@bp.post("/register")
def register_post():
    email = (request.form.get("email") or "").strip().lower()
    name = (request.form.get("name") or "").strip()
    password = request.form.get("password") or ""
    password2 = request.form.get("password2") or ""

    if not email or "@" not in email:
        flash("Email inválido.", "error")
        return redirect(url_for("auth.register_page"))

    if len(password) < 8:
        flash("La contraseña debe tener al menos 8 caracteres.", "error")
        return redirect(url_for("auth.register_page"))

    if password != password2:
        flash("Las contraseñas no coinciden.", "error")
        return redirect(url_for("auth.register_page"))

    exists = db.session.query(User).filter(User.email == email).first()
    if exists:
        flash("Ese email ya está registrado. Inicia sesión.", "error")
        return redirect(url_for("auth.login_page"))

    user = User(
        email=email,
        display_name=name or None,
        password_hash=generate_password_hash(password),
        is_verified=False,
        is_active=True,
        created_at=dt.datetime.utcnow(),
        updated_at=dt.datetime.utcnow(),
    )
    db.session.add(user)
    db.session.commit()

    token = secrets.token_urlsafe(32)
    expires = dt.datetime.utcnow() + dt.timedelta(hours=24)

    vt = EmailVerificationToken(
        user_id=user.id,
        token=token,
        expires_at=expires,
        used_at=None,
        created_at=dt.datetime.utcnow(),
    )
    db.session.add(vt)
    db.session.commit()

    verify_link = urljoin(_base_url(), f"auth/verify?token={token}")

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px">
      <h2>Verifica tu correo para activar PolyScribe</h2>
      <p>Haz clic aquí:</p>
      <p><a href="{verify_link}" style="background:#0b62e0;color:#fff;padding:10px 14px;border-radius:8px;text-decoration:none;font-weight:800">Verificar correo</a></p>
      <p>Si no abre, copia y pega:</p>
      <p><a href="{verify_link}">{verify_link}</a></p>
      <p style="color:#6b7280;font-size:12px">Expira en 24 horas.</p>
    </div>
    """
    _send_email(email, "Verifica tu correo - PolyScribe", html)

    flash("Cuenta creada. Revisa tu correo para verificar y luego inicia sesión.", "success")
    return redirect(url_for("auth.login_page"))


@bp.get("/verify")
def verify_email():
    token = (request.args.get("token") or "").strip()
    if not token:
        return render_template("auth/verify_result.html", ok=False, msg="Token faltante.")

    vt = db.session.query(EmailVerificationToken).filter(EmailVerificationToken.token == token).first()
    if not vt:
        return render_template("auth/verify_result.html", ok=False, msg="Token inválido.")

    if vt.used_at is not None:
        return render_template("auth/verify_result.html", ok=True, msg="Tu correo ya estaba verificado.")

    if dt.datetime.utcnow() > vt.expires_at:
        return render_template("auth/verify_result.html", ok=False, msg="Token expirado. Regístrate de nuevo.")

    user = db.session.get(User, int(vt.user_id))
    if not user:
        return render_template("auth/verify_result.html", ok=False, msg="Usuario no existe.")

    user.is_verified = True
    user.updated_at = dt.datetime.utcnow()
    vt.used_at = dt.datetime.utcnow()
    db.session.commit()

    return render_template("auth/verify_result.html", ok=True, msg="✅ Verificación exitosa. Ya puedes iniciar sesión.")


@bp.get("/login")
def login_page():
    return render_template("auth/login.html")


@bp.post("/login")
def login_post():
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    user = db.session.query(User).filter(User.email == email).first()
    if not user:
        flash("Credenciales inválidas.", "error")
        return redirect(url_for("auth.login_page"))

    if current_app.config.get("AUTH_REQUIRE_VERIFIED_EMAIL", True) and not user.is_verified:
        flash("Debes verificar tu correo antes de entrar.", "error")
        return redirect(url_for("auth.login_page"))

    if not user.password_hash or not check_password_hash(user.password_hash, password):
        flash("Credenciales inválidas.", "error")
        return redirect(url_for("auth.login_page"))

    user.last_login_at = dt.datetime.utcnow()
    db.session.commit()

    _login_user(user)
    return redirect("/")


@bp.get("/logout")
def logout():
    _logout_user()
    return redirect(url_for("auth.login_page"))


# =========================
# OLVIDÉ MI CONTRASEÑA
# =========================

@bp.get("/forgot")
def forgot_page():
    return render_template("auth/forgot.html")


@bp.post("/forgot")
def forgot_post():
    email = (request.form.get("email") or "").strip().lower()
    generic_ok = "Si el email existe, enviaremos un enlace para restablecer la contraseña."

    if not email or "@" not in email:
        flash(generic_ok, "success")
        return redirect(url_for("auth.login_page"))

    user = db.session.query(User).filter(User.email == email).first()
    if not user:
        flash(generic_ok, "success")
        return redirect(url_for("auth.login_page"))

    token = secrets.token_urlsafe(32)
    expires = dt.datetime.utcnow() + dt.timedelta(minutes=30)

    pr = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=expires,
        used_at=None,
        created_at=dt.datetime.utcnow(),
    )
    db.session.add(pr)
    db.session.commit()

    reset_link = urljoin(_base_url(), f"auth/reset?token={token}")

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px">
      <h2>Restablecer contraseña</h2>
      <p>Haz clic para crear una nueva contraseña:</p>
      <p><a href="{reset_link}" style="background:#22c55e;color:#0b111d;padding:10px 14px;border-radius:8px;text-decoration:none;font-weight:900">Crear nueva contraseña</a></p>
      <p>Si no abre, copia y pega:</p>
      <p><a href="{reset_link}">{reset_link}</a></p>
      <p style="color:#6b7280;font-size:12px">Expira en 30 minutos.</p>
    </div>
    """
    _send_email(email, "Restablecer contraseña - PolyScribe", html)

    flash(generic_ok, "success")
    return redirect(url_for("auth.login_page"))


@bp.get("/reset")
def reset_page():
    token = (request.args.get("token") or "").strip()
    if not token:
        return render_template("auth/reset_result.html", ok=False, msg="Token faltante.")

    pr = db.session.query(PasswordResetToken).filter(PasswordResetToken.token == token).first()
    if not pr:
        return render_template("auth/reset_result.html", ok=False, msg="Token inválido.")

    if pr.used_at is not None:
        return render_template("auth/reset_result.html", ok=False, msg="Este enlace ya fue usado.")

    if dt.datetime.utcnow() > pr.expires_at:
        return render_template("auth/reset_result.html", ok=False, msg="Enlace expirado. Solicita otro.")

    return render_template("auth/reset_form.html", token=token)


@bp.post("/reset")
def reset_post():
    token = (request.form.get("token") or "").strip()
    password = request.form.get("password") or ""
    password2 = request.form.get("password2") or ""

    if len(password) < 8:
        flash("La contraseña debe tener al menos 8 caracteres.", "error")
        return redirect(url_for("auth.reset_page", token=token))

    if password != password2:
        flash("Las contraseñas no coinciden.", "error")
        return redirect(url_for("auth.reset_page", token=token))

    pr = db.session.query(PasswordResetToken).filter(PasswordResetToken.token == token).first()
    if not pr:
        return render_template("auth/reset_result.html", ok=False, msg="Token inválido.")

    if pr.used_at is not None:
        return render_template("auth/reset_result.html", ok=False, msg="Este enlace ya fue usado.")

    if dt.datetime.utcnow() > pr.expires_at:
        return render_template("auth/reset_result.html", ok=False, msg="Enlace expirado. Solicita otro.")

    user = db.session.get(User, int(pr.user_id))
    if not user:
        return render_template("auth/reset_result.html", ok=False, msg="Usuario no existe.")

    user.password_hash = generate_password_hash(password)
    user.updated_at = dt.datetime.utcnow()
    pr.used_at = dt.datetime.utcnow()
    db.session.commit()

    return render_template("auth/reset_result.html", ok=True, msg="✅ Contraseña actualizada. Ya puedes iniciar sesión.")
