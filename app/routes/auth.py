# app/routes/auth.py
from __future__ import annotations
from datetime import datetime
from flask import Blueprint, request, session, jsonify, current_app, redirect, url_for, render_template
from werkzeug.security import check_password_hash
from app.extensions import db
from app.models_user import User  # tu modelo de usuarios

bp = Blueprint("auth", __name__)

@bp.route("/auth/ping", methods=["GET"])
def ping():
    return jsonify(ok=True, msg="pong")

@bp.route("/auth/diag", methods=["GET"])
def diag():
    return jsonify(ok=True, diag={
        "has_secret_key": bool(current_app.secret_key),
        "session_cookie_secure": bool(current_app.config.get("SESSION_COOKIE_SECURE")),
        "url_map_count": len(list(current_app.url_map.iter_rules())),
    })

# ---- VISTAS HTML (evita 404 en Entrar / Registro) ----
@bp.get("/auth/login")
def login_page():
    # si tienes templates/auth_login.html, lo renderiza; si no, redirige a /devlogin
    try:
        return render_template("auth_login.html")
    except Exception:
        return redirect(url_for("auth.devlogin"))

@bp.get("/auth/register")
def register_page():
    # redirige a devlogin (útil en local)
    return redirect(url_for("auth.devlogin"))

@bp.get("/devlogin")
def devlogin():
    # muestra el formulario simple de devlogin.html
    return render_template("devlogin.html")

@bp.get("/devlogin/set")
def devlogin_set():
    uid = request.args.get("uid") or request.args.get("user_id") or "1"
    try:
        uid_int = int(uid)
    except Exception:
        return jsonify(ok=False, error="uid inválido"), 400
    session["uid"] = uid_int
    session["user_id"] = uid_int
    # vuelve a Home con ?user_id por compatibilidad con el frontend actual
    return redirect(url_for("pages.index", user_id=uid))

# ---- API AUTH (JSON) ----
def _serialize_user(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "is_active": getattr(u, "is_active", True),
        "is_verified": getattr(u, "is_verified", True),
        "plan_tier": getattr(u, "plan_tier", "free"),
        "minute_quota": getattr(u, "minute_quota", 0),
        "minutes_used": getattr(u, "minutes_used", 0),
        "last_login_at": getattr(u, "last_login_at", None),
    }

@bp.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or request.form or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify(ok=False, error="email y password requeridos"), 400

    u = db.session.query(User).filter(User.email == email).first()
    if not u:
        return jsonify(ok=False, error="Usuario no encontrado"), 401

    pwh = getattr(u, "password_hash", None)
    if pwh and not check_password_hash(pwh, password):
        return jsonify(ok=False, error="Credenciales inválidas"), 401

    try:
        setattr(u, "last_login_at", datetime.utcnow())
        db.session.commit()
    except Exception:
        db.session.rollback()

    # compatibilidad: ambas claves de sesión
    session["uid"] = int(u.id)
    session["user_id"] = int(u.id)

    return jsonify(ok=True, user=_serialize_user(u))

@bp.route("/auth/me", methods=["GET"])
def me():
    uid = session.get("uid") or session.get("user_id")
    if not uid:
        return jsonify(authenticated=False)
    u = db.session.get(User, int(uid))
    if not u:
        return jsonify(authenticated=False)
    return jsonify(authenticated=True, user=_serialize_user(u))

@bp.route("/auth/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    return jsonify(ok=True)
