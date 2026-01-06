# app/routes/auth.py
from __future__ import annotations

import datetime as dt
import secrets

from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, session

from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models_auth import User, EmailVerificationToken, PasswordResetToken
from app.services.mailer import send_email

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _base_url() -> str:
    # ✅ IMPORTANTE: usa SIEMPRE www para evitar NXDOMAIN en links de correo
    base = (current_app.config.get("APP_BASE_URL") or "").strip().rstrip("/")
    if not base:
        base = "https://www.getpolyscribe.com"
    # Fuerza www
    if base.startswith("https://getpolyscribe.com"):
        base = base.replace("https://getpolyscribe.com", "https://www.getpolyscribe.com")
    if base.startswith("http://getpolyscribe.com"):
        base = base.replace("http://getpolyscribe.com", "https://www.getpolyscribe.com")
    return base


def _require_verified() -> bool:
    return bool(current_app.config.get("AUTH_REQUIRE_VERIFIED_EMAIL", True))


def current_user_id() -> int | None:
    uid = session.get("user_id")
    try:
        return int(uid) if uid is not None else None
    except Exception:
        return None


def _login_user(user: User) -> None:
    session["user_id"] = user.id
    session["user_email"] = user.email


def _logout_user() -> None:
    session.pop("user_id", None)
    session.pop("user_email", None)


@bp.get("/register")
def register_page():
    return render_template("auth/register.html")


@bp.post("/register")
def register_submit():
    email = (request.form.get("email") or "").strip().lower()
    name = (request.form.get("name") or "").strip()
    password = request.form.get("password") or ""
    password2 = request.form.get("password2") or ""

    if not email or "@" not in email:
        flash("Correo inválido.", "error")
        return redirect(url_for("auth.register_page"))

    if len(password) < 8:
        flash("La contraseña debe tener al menos 8 caracteres.", "error")
        return redirect(url_for("auth.register_page"))

    if password != password2:
        flash("Las contraseñas no coinciden.", "error")
        return redirect(url_for("auth.register_page"))

    existing = db.session.query(User).filter(User.email == email).first()
    if existing:
        flash("Ese correo ya está registrado. Inicia sesión.", "error")
        return redirect(url_for("auth.login_page"))

    user = User(
        email=email,
        name=name or None,
        password_hash=generate_password_hash(password),
        is_verified=False,
    )
    db.session.add(user)
    db.session.commit()

    # token verificación
    token = secrets.token_urlsafe(32)
    expires = dt.datetime.utcnow() + dt.timedelta(hours=24)

    vt = EmailVerificationToken(
        user_id=user.id,
        token=token,
        expires_at=expires,
        used_at=None,
    )
    db.session.add(vt)
    db.session.commit()

    verify_link = f"{_base_url()}/auth/verify?token={token}"

    subject = "PolyScribe · Verifica tu correo"
    html = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6">
      <h2>Verifica tu correo</h2>
      <p>Hola{(" " + name) if name else ""},</p>
      <p>Para activar tu cuenta, confirma tu email:</p>
      <p><a href="{verify_link}" style="display:inline-block;padding:10px 14px;background:#0b62e0;color:#fff;border-radius:10px;text-decoration:none;font-weight:700">Verificar correo</a></p>
      <p style="color:#555;font-size:13px">Si no solicitaste esto, ignora este email.</p>
      <p style="color:#555;font-size:13px">Enlace directo: {verify_link}</p>
    </div>
    """
    send_email(email, subject, html)

    flash("Te enviamos un correo de verificación. Revisa tu bandeja (y spam).", "success")
    return redirect(url_for("auth.login_page"))


@bp.get("/verify")
def verify_email():
    token = (request.args.get("token") or "").strip()
    if not token:
        return render_template("auth/verify_result.html", ok=False, message="Token inválido.")

    vt = db.session.query(EmailVerificationToken).filter(EmailVerificationToken.token == token).first()
    if not vt:
        return render_template("auth/verify_result.html", ok=False, message="Token no encontrado.")

    if vt.used_at is not None:
        return render_template("auth/verify_result.html", ok=True, message="Tu correo ya estaba verificado. Ya puedes iniciar sesión.")

    if dt.datetime.utcnow() > vt.expires_at:
        return render_template("auth/verify_result.html", ok=False, message="Token expirado. Regístrate nuevamente o solicita otro enlace.")

    user = db.session.get(User, vt.user_id)
    if not user:
        return render_template("auth/verify_result.html", ok=False, message="Usuario no encontrado.")

    user.is_verified = True
    vt.used_at = dt.datetime.utcnow()
    db.session.commit()

    return render_template("auth/verify_result.html", ok=True, message="✅ Verificación exitosa. Ya puedes iniciar sesión.")


@bp.get("/login")
def login_page():
    return render_template("auth/login.html")


@bp.post("/login")
def login_submit():
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    user = db.session.query(User).filter(User.email == email).first()
    if not user or not check_password_hash(user.password_hash, password):
        flash("Correo o contraseña incorrectos.", "error")
        return redirect(url_for("auth.login_page"))

    if _require_verified() and not user.is_verified:
        flash("Debes verificar tu correo antes de iniciar sesión.", "error")
        return redirect(url_for("auth.login_page"))

    _login_user(user)
    return redirect(url_for("pages.index"))  # Ajusta si tu endpoint raíz es distinto


@bp.get("/logout")
def logout():
    _logout_user()
    flash("Sesión cerrada.", "success")
    return redirect(url_for("auth.login_page"))


# =========================
# RESET PASSWORD (PROD)
# =========================

@bp.get("/forgot")
def forgot_page():
    return render_template("auth/forgot.html")


@bp.post("/forgot")
def forgot_submit():
    email = (request.form.get("email") or "").strip().lower()

    # Mensaje neutro SIEMPRE
    neutral_msg = "Si el correo existe, te enviamos un enlace para restablecer tu contraseña."

    if not email or "@" not in email:
        flash(neutral_msg, "success")
        return redirect(url_for("auth.forgot_page"))

    user = db.session.query(User).filter(User.email == email).first()
    if user:
        token = secrets.token_urlsafe(32)
        expires = dt.datetime.utcnow() + dt.timedelta(minutes=30)

        rt = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=expires,
            used_at=None,
        )
        db.session.add(rt)
        db.session.commit()

        reset_link = f"{_base_url()}/auth/reset?token={token}"

        subject = "PolyScribe · Restablecer contraseña"
        html = f"""
        <div style="font-family:Arial,sans-serif;line-height:1.6">
          <h2>Restablecer contraseña</h2>
          <p>Recibimos una solicitud para cambiar tu contraseña.</p>
          <p><a href="{reset_link}" style="display:inline-block;padding:10px 14px;background:#22c55e;color:#0b111d;border-radius:10px;text-decoration:none;font-weight:800">Crear nueva contraseña</a></p>
          <p style="color:#555;font-size:13px">Este enlace expira en 30 minutos.</p>
          <p style="color:#555;font-size:13px">Enlace directo: {reset_link}</p>
        </div>
        """
        send_email(email, subject, html)

    flash(neutral_msg, "success")
    return redirect(url_for("auth.login_page"))


@bp.get("/reset")
def reset_page():
    token = (request.args.get("token") or "").strip()
    if not token:
        return render_template("auth/reset.html", ok=False, token="", message="Token inválido.")

    rt = db.session.query(PasswordResetToken).filter(PasswordResetToken.token == token).first()
    if not rt:
        return render_template("auth/reset.html", ok=False, token="", message="Token no encontrado.")

    if rt.used_at is not None:
        return render_template("auth/reset.html", ok=False, token="", message="Este enlace ya fue usado. Solicita uno nuevo.")

    if dt.datetime.utcnow() > rt.expires_at:
        return render_template("auth/reset.html", ok=False, token="", message="Enlace expirado. Solicita uno nuevo.")

    return render_template("auth/reset.html", ok=True, token=token, message="")


@bp.post("/reset")
def reset_submit():
    token = (request.form.get("token") or "").strip()
    password = request.form.get("password") or ""
    password2 = request.form.get("password2") or ""

    if len(password) < 8:
        return render_template("auth/reset.html", ok=True, token=token, message="La contraseña debe tener al menos 8 caracteres.")

    if password != password2:
        return render_template("auth/reset.html", ok=True, token=token, message="Las contraseñas no coinciden.")

    rt = db.session.query(PasswordResetToken).filter(PasswordResetToken.token == token).first()
    if not rt or rt.used_at is not None or dt.datetime.utcnow() > rt.expires_at:
        return render_template("auth/reset.html", ok=False, token="", message="Token inválido o expirado.")

    user = db.session.get(User, rt.user_id)
    if not user:
        return render_template("auth/reset.html", ok=False, token="", message="Usuario no encontrado.")

    user.password_hash = generate_password_hash(password)
    rt.used_at = dt.datetime.utcnow()
    db.session.commit()

    flash("✅ Contraseña actualizada. Ya puedes iniciar sesión.", "success")
    return redirect(url_for("auth.login_page"))
