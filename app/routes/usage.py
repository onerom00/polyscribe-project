# app/routes/usage.py
from __future__ import annotations

import os
import json

from flask import Blueprint, current_app, jsonify, request

from app.models_payment import Payment

bp = Blueprint("usage", __name__)


def _get_current_user_id() -> str | None:
    """
    Intenta obtener el user_id desde:
    - Header X-User-Id (lo usamos en el frontend)
    - query param ?user_id=
    - variable de entorno DEV_USER_ID (para pruebas locales)
    """
    uid = request.headers.get("X-User-Id") or request.args.get("user_id")
    if uid:
        return str(uid)

    dev_id = os.getenv("DEV_USER_ID")
    if dev_id:
        return str(dev_id)

    return None


def _sum_paid_minutes_for_user(user_id: str) -> int:
    """
    Suma los minutos comprados para un usuario a partir de la tabla Payment.

    Como el user_id real (correo) lo guardamos dentro de raw_payload en JSON,
    leemos todos los payments COMPLETED y filtramos por ese campo.
    Esto es suficiente para un MVP; si luego quieres escalar, podemos
    normalizar y guardar el user_id en una columna dedicada.
    """
    if not user_id:
        return 0

    total = 0
    payments = Payment.query.filter_by(status="COMPLETED", provider="paypal").all()
    for p in payments:
        if not p.raw_payload:
            continue
        try:
            data = json.loads(p.raw_payload)
        except Exception:
            continue
        if data.get("user_id") == user_id:
            total += p.minutes or 0
    return total


@bp.get("/api/usage/balance")
def usage_balance():
    """
    Devuelve el saldo de minutos del usuario actual.

    Por ahora:
    - FREE_TIER_MINUTES viene de .env (por defecto 10)
    - free_used = 0 (TODO: descontar minutos usados por jobs)
    - paid_purchased = suma de minutos en Payment COMPLETED
    - paid_used = 0 (TODO: descontar minutos consumidos del saldo de pago)

    Estructura de respuesta:

    {
      "user_id": "...",
      "free": { "included": 10, "used": 0, "remaining": 10 },
      "paid": { "purchased": 60, "used": 0, "remaining": 60 },
      "total_remaining": 70
    }
    """
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"error": "Falta user_id y no hay DEV_USER_ID configurado."}), 400

    free_included = int(
        os.getenv("FREE_TIER_MINUTES")
        or current_app.config.get("FREE_TIER_MINUTES", 10)
    )

    # TODO: integrar minutos usados reales desde jobs / UsageLedger
    free_used = 0
    free_remaining = max(free_included - free_used, 0)

    paid_purchased = _sum_paid_minutes_for_user(user_id)
    paid_used = 0  # TODO: cuando haya consumo medido, restar aquí
    paid_remaining = max(paid_purchased - paid_used, 0)

    total_remaining = free_remaining + paid_remaining

    return jsonify(
        {
            "user_id": user_id,
            "free": {
                "included": free_included,
                "used": free_used,
                "remaining": free_remaining,
            },
            "paid": {
                "purchased": paid_purchased,
                "used": paid_used,
                "remaining": paid_remaining,
            },
            "total_remaining": total_remaining,
        }
    )

