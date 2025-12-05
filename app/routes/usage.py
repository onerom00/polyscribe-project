# app/routes/usage.py
from __future__ import annotations

from typing import Optional

from flask import Blueprint, current_app, jsonify, request

from app import db  # por si más adelante quieres rutas de consumo
from app.models import UsageLedger


bp = Blueprint("usage", __name__, url_prefix="/api/usage")


# ---------------------------------------------------------
# Helper: user_id coherente en toda la app
# ---------------------------------------------------------
def _get_user_id() -> str:
    """
    Obtiene el user_id desde:
      1) Header 'X-User-Id'
      2) Query string ?user_id=...
      3) Fallback: 'guest'
    """
    uid = request.headers.get("X-User-Id")
    if not uid:
        uid = request.args.get("user_id")

    if not uid:
        uid = "guest"

    return uid


# ---------------------------------------------------------
# GET /api/usage/balance
# ---------------------------------------------------------
@bp.get("/balance")
def usage_balance():
    """
    Devuelve el saldo de minutos del usuario:

      {
        "user_id": "guest",
        "free_quota": 10,
        "free_used": 3,
        "free_remaining": 7,
        "paid_minutes": 120,
        "total_remaining": 127
      }

    Asume que el modelo UsageLedger tiene, al menos:
      - user_id
      - free_minutes_used (int, minutos gratuitos consumidos)
      - paid_minutes      (int, minutos de pago disponibles)
    """
    user_id = _get_user_id()
    free_quota = int(current_app.config.get("FREE_TIER_MINUTES", 10))

    ledger: Optional[UsageLedger] = UsageLedger.query.filter_by(
        user_id=user_id
    ).first()

    if not ledger:
        free_used = 0
        paid_minutes = 0
    else:
        free_used = getattr(ledger, "free_minutes_used", 0) or 0
        paid_minutes = getattr(ledger, "paid_minutes", 0) or 0

    free_remaining = max(free_quota - free_used, 0)
    total_remaining = free_remaining + paid_minutes

    return jsonify(
        {
            "user_id": user_id,
            "free_quota": free_quota,
            "free_used": free_used,
            "free_remaining": free_remaining,
            "paid_minutes": paid_minutes,
            "total_remaining": total_remaining,
        }
    )
