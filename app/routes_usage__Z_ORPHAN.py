# app/routes/usage.py
from flask import Blueprint, jsonify, request, current_app
from .. import db
from ..models import User

bp = Blueprint("usage", __name__, url_prefix="")

@bp.get("/api/usage/balance")
def usage_balance():
    raw = (
        request.headers.get("X-User-Id")
        or request.args.get("user_id")
        or (current_app.config.get("DEV_USER_ID") and str(current_app.config.get("DEV_USER_ID")))
    )
    try:
        uid = int(raw) if raw is not None else None
    except (TypeError, ValueError):
        uid = None

    user = db.session.get(User, uid) if uid else None
    if not user:
        # Devuelve 0/0 para no romper UI si no hay user
        return jsonify({"used_seconds": 0, "allowance_seconds": 0, "plan_tier": "free"})

    used_min = int(user.minutes_used or 0)
    quota_min = int(user.minute_quota or 0)

    return jsonify({
        "used_seconds": used_min * 60,
        "allowance_seconds": quota_min * 60,
        "plan_tier": user.plan_tier or "free",
    })
