# app/routes/auth_api.py
from __future__ import annotations

from flask import Blueprint, jsonify, session
from app.extensions import db
from app.models_user import User

bp = Blueprint("auth_api", __name__, url_prefix="/api/auth")


@bp.get("/me")
def me():
    """
    Fuente de verdad: SESIÓN.
    Devuelve si el usuario está autenticado y su user_id real.
    """
    raw = session.get("user_id") or session.get("uid")
    uid = str(raw).strip() if raw else ""

    if not uid:
        return jsonify({"ok": True, "authenticated": False, "user_id": None, "email": None}), 200

    # (Opcional) traer email para UI si lo quieres mostrar
    email = None
    try:
        user = db.session.get(User, int(uid))
        if user:
            email = getattr(user, "email", None)
    except Exception:
        email = None

    return jsonify({"ok": True, "authenticated": True, "user_id": uid, "email": email}), 200
