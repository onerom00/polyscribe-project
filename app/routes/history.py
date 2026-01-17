# app/routes/history.py
from __future__ import annotations

import os
from flask import Blueprint, jsonify, request, session

from app import db
from app.models import AudioJob

bp = Blueprint("history", __name__, url_prefix="/api/history")


def _get_user_id() -> str:
    raw = (
        session.get("user_id")
        or session.get("uid")
        or request.headers.get("X-User-Id")
        or request.args.get("user_id")
        or os.getenv("DEV_USER_ID", "")
    )
    s = str(raw).strip() if raw else ""
    return s or "guest"


@bp.get("")
def history_list():
    user_id = _get_user_id()
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
