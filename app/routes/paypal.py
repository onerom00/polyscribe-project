# app/routes/paypal.py
from __future__ import annotations

import json
from typing import Optional

from flask import (
    Blueprint,
    current_app,
    jsonify,
    request,
)
from app import db
from app.models import UsageLedger
from app.models_payment import Payment


# Blueprint de páginas (si quieres pantallas personalizadas /paypal/thanks, etc.)
bp = Blueprint("paypal_pages", __name__)

# Blueprint de API
api_bp = Blueprint("paypal_api", __name__, url_prefix="/api/paypal")


# ---------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------
def _get_user_id() -> str:
    """
    Obtiene el user_id de manera consistente:

    1. Header 'X-User-Id' (si lo envía el frontend)
    2. Query string ?user_id=...
    3. Fallback: 'guest'
    """
    uid = request.headers.get("X-User-Id")
    if not uid:
        uid = request.args.get("user_id")

    if not uid:
        uid = "guest"

    return uid


def _get_or_create_ledger(user_id: str) -> UsageLedger:
    """
    Devuelve el registro de UsageLedger para el usuario,
    creándolo si no existe.
    """
    ledger: Optional[UsageLedger] = UsageLedger.query.filter_by(
        user_id=user_id
    ).first()

    if not ledger:
        ledger = UsageLedger(
            user_id=user_id,
            free_minutes_used=0,
            paid_minutes=0,
        )
        db.session.add(ledger)

    return ledger


# ---------------------------------------------------------
# Rutas de páginas (opcionales, pero útiles)
# ---------------------------------------------------------
@bp.route("/paypal/thanks")
def paypal_thanks():
    return "Pago completado. Puedes cerrar esta ventana."


@bp.route("/paypal/cancel")
def paypal_cancel():
    return "El pago fue cancelado. Puedes cerrar esta ventana."


# ---------------------------------------------------------
# API: configuración PayPal
# ---------------------------------------------------------
@api_bp.get("/config")
def paypal_config():
    """
    Devuelve la configuración necesaria para inicializar el SDK de PayPal
    en el frontend (client_id, currency, etc.)
    """
    enabled = bool(current_app.config.get("PAYPAL_ENABLED", False))
    if not enabled:
        return jsonify({"enabled": False}), 200

    return jsonify(
        {
            "enabled": True,
            "client_id": current_app.config.get("PAYPAL_CLIENT_ID"),
            "currency": current_app.config.get("PAYPAL_CURRENCY", "USD"),
            "env": current_app.config.get("PAYPAL_ENV", "sandbox"),
        }
    )


# ---------------------------------------------------------
# API: captura de pago (desde payments.js con Buttons)
# ---------------------------------------------------------
@api_bp.post("/capture")
def paypal_capture():
    """
    Endpoint llamado por app/static/js/payments.js después de que
    el SDK de PayPal hace order.capture().

    Espera un JSON como:
      {
        "order_id": "...",
        "sku": "starter_60",
        "minutes": 60,
        "amount": "9.00"
      }

    Este endpoint:
      1) Registra el Payment (si no existía)
      2) Marca el pago como 'captured'
      3) Acredita los minutos en UsageLedger.paid_minutes
      4) Es idempotente: si el order_id ya existe, no duplica el saldo
    """
    if not current_app.config.get("PAYPAL_ENABLED", False):
        return (
            jsonify({"error": "PayPal no está configurado en el servidor."}),
            400,
        )

    data = request.get_json(silent=True) or {}

    order_id = data.get("order_id")
    sku = data.get("sku")
    minutes_raw = data.get("minutes")
    amount_raw = data.get("amount")

    try:
        minutes = int(minutes_raw or 0)
    except (TypeError, ValueError):
        minutes = 0

    try:
        amount = float(amount_raw or 0)
    except (TypeError, ValueError):
        amount = 0.0

    if not order_id or minutes <= 0 or amount <= 0:
        return (
            jsonify(
                {
                    "error": "Datos de pago incompletos. "
                    "Se requiere order_id, minutes > 0 y amount > 0."
                }
            ),
            400,
        )

    user_id = _get_user_id()
    currency = current_app.config.get("PAYPAL_CURRENCY", "USD")

    # -----------------------------------------------------
    # Idempotencia: si ya existe el pago con ese order_id,
    # NO volvemos a acreditar minutos.
    # -----------------------------------------------------
    existing: Optional[Payment] = Payment.query.filter_by(
        provider_order_id=order_id
    ).first()

    if existing:
        # Aseguramos que quede 'captured' pero no duplicamos minutos
        if existing.status != "captured":
            existing.status = "captured"
            db.session.commit()

        return jsonify(
            {
                "ok": True,
                "user_id": existing.user_id,
                "minutes_added": 0,  # ya estaban acreditados
                "message": "Orden ya registrada previamente.",
            }
        )

    # -----------------------------------------------------
    # Crear Payment nuevo + acreditar minutos
    # -----------------------------------------------------
    payment = Payment(
        user_id=user_id,
        provider="paypal",
        provider_order_id=order_id,
        sku=sku,
        minutes=minutes,
        amount=amount,
        currency=currency,
        status="captured",
        raw_payload=json.dumps(data, ensure_ascii=False),
    )
    db.session.add(payment)

    # Actualizar UsageLedger
    ledger = _get_or_create_ledger(user_id)
    if ledger.paid_minutes is None:
        ledger.paid_minutes = 0
    ledger.paid_minutes += minutes

    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "user_id": user_id,
            "minutes_added": minutes,
            "total_paid_minutes": ledger.paid_minutes,
        }
    )
