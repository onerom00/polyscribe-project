# app/routes/history.py
from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from app import db
from app.models import AudioJob

bp = Blueprint("history", __name__, url_prefix="/api/history")


def _require_user_id() -> str | None:
    """
    Historial debe ser 100% por sesión real.
    Si no hay sesión => None.
    """
    uid = session.get("user_id")
    if not uid:
        return None
    s = str(uid).strip()
    if not s:
        return None
    return s


@bp.get("")
def history_list():
    user_id = _require_user_id()
    if not user_id:
        # ✅ frontend debe mostrar: “Inicia sesión...”
        return jsonify({"ok": False, "error": "auth_required"}), 401

    limit = int(request.args.get("limit", "100") or 100)
    limit = max(1, min(limit, 500))

    q = (
        db.session.query(AudioJob)
        .filter(AudioJob.user_id == user_id)
        .order_by(AudioJob.created_at.desc())
        .limit(limit)
    )

    items = [j.to_dict() for j in q.all()]
    return jsonify({"ok": True, "items": items, "count": len(items)})
