# app/routes/usage.py
from __future__ import annotations

import os
from typing import Optional

from flask import Blueprint, current_app, jsonify, request, session

from app import db
from app.models import AudioJob
from app.models_payment import Payment

bp = Blueprint("usage", __name__, url_prefix="/api/usage")

MB = 1024 * 1024
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100") or 100)


# ---------------------------------------------------------
# Helper: user_id COHERENTE en toda la app
#   Igual que en app/routes/jobs.py
# ---------------------------------------------------------
def _get_user_id() -> str:
    """
    Obtiene el user_id desde, en este orden:
      1) session["user_id"] o session["uid"]
      2) Header 'X-User-Id'
      3) Query string ?user_id=...
      4) Fallback: DEV_USER_ID (modo dev)
      5) Último fallback: 'guest'
    """
    raw = (
        session.get("user_id")
        or session.get("uid")
        or request.headers.get("X-User-Id")
        or request.args.get("user_id")
        or os.getenv("DEV_USER_ID", "")
    )
    s = str(raw).strip() if raw else ""
    return s or "guest"


# ---------------------------------------------------------
# GET /api/usage/balance
#   Respuesta:
#   {
#     "ok": true,
#     "used_seconds": ...,
#     "allowance_seconds": ...,
#     "file_limit_bytes": ...
#   }
# ---------------------------------------------------------
@bp.get("/balance")
def usage_balance():
    user_id = _get_user_id()
    free_min = int(current_app.config.get("FREE_TIER_MINUTES", 10))

    # Minutos pagados
    paid_min = 0
    try:
        q = db.session.query(Payment).filter(
            Payment.user_id == user_id,
            Payment.status == "captured",
        )
        paid_min = sum(int(p.minutes or 0) for p in q.all())
    except Exception as e:
        current_app.logger.error("usage_balance: error leyendo pagos: %s", e)
        paid_min = 0

    # Segundos usados (de todos los jobs de este user)
    used_seconds = 0
    try:
        qj = db.session.query(AudioJob).filter(AudioJob.user_id == user_id)
        used_seconds = sum(int(j.duration_seconds or 0) for j in qj.all())
    except Exception as e:
        current_app.logger.error("usage_balance: error leyendo jobs: %s", e)
        used_seconds = 0

    allowance_min = free_min + paid_min
    allowance_seconds = int(allowance_min * 60)

    # Log de depuración para ver exactamente qué está pasando
    current_app.logger.info(
        "USAGE_BALANCE uid=%s used_seconds=%.2f allowance_seconds=%.2f free_min=%s paid_min=%s",
        user_id,
        used_seconds,
        allowance_seconds,
        free_min,
        paid_min,
    )

    return jsonify(
        {
            "ok": True,
            "used_seconds": int(used_seconds),
            "allowance_seconds": allowance_seconds,
            "file_limit_bytes": int(MAX_UPLOAD_MB * MB),
        }
    )
