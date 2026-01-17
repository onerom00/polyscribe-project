# app/routes/paypal.py
from __future__ import annotations

import json
from typing import Dict, Any

from flask import (
    Blueprint,
    current_app,
    jsonify,
    request,
)

from app import db
from app.models_payment import Payment

bp = Blueprint("paypal_pages", __name__, url_prefix="/paypal")
api_bp = Blueprint("paypal_api", __name__, url_prefix="/api/paypal")


# -----------------------------------------------------
# Helper para obtener el user_id de forma consistente
# -----------------------------------------------------
def _get_user_id() -> str:
    """
    Intenta resolver el user_id desde:
      1) Cabecera X-User-Id
      2) Query string ?user_id=...
      3) JSON body {"user_id": "..."}
      4) Fallback "guest"
    """
    uid = request.headers.get("X-User-Id") or request.args.get("user_id")

    if not uid:
        try:
            data = request.get_json(silent=True) or {}
        except Exception:
            data = {}
        uid = data.get("user_id")

    if not uid:
        uid = "guest"

    return uid


# -----------------------------------------------------
# API: CONFIG
#  GET /api/paypal/config
# Usado por static/js/payments.js para cargar el SDK
# -----------------------------------------------------
@api_bp.get("/config")
def paypal_config():
    if not current_app.config.get("PAYPAL_ENABLED", False):
        return jsonify({"enabled": False}), 200

    return jsonify(
        {
            "enabled": True,
            "client_id": current_app.config.get("PAYPAL_CLIENT_ID"),
            "currency": current_app.config.get("PAYPAL_CURRENCY", "USD"),
            "env": current_app.config.get("PAYPAL_ENV", "sandbox"),
        }
    )


# -----------------------------------------------------
# API: CAPTURE (notificación desde payments.js)
#  POST /api/paypal/capture
#  Body JSON: { order_id, sku, minutes, amount }
#
# Ojo: el capture real lo hace el JS del navegador.
# Aquí SOLO registramos el pago y abonamos minutos.
# -----------------------------------------------------
@api_bp.post("/capture")
def paypal_capture():
    if not current_app.config.get("PAYPAL_ENABLED", False):
        return jsonify({"error": "PayPal no está habilitado en el servidor."}), 400

    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}

    order_id = data.get("order_id")
    sku = data.get("sku")
    minutes = int(data.get("minutes") or 0)
    amount_str = str(data.get("amount") or "0")

    if not order_id or minutes <= 0:
        return jsonify({"error": "Datos de pago incompletos."}), 400

    try:
        amount_usd = float(amount_str)
    except ValueError:
        amount_usd = 0.0

    user_id = _get_user_id()
    app = current_app

    app.logger.info(
        "PayPal capture notify: user=%s order_id=%s sku=%s minutes=%s amount=%s",
        user_id,
        order_id,
        sku,
        minutes,
        amount_usd,
    )

    # ¿Ya registramos este order_id? Evitamos duplicados.
    existing = Payment.query.filter_by(order_id=order_id).first()
    if existing:
        app.logger.warning("PayPal capture duplicado para order_id=%s", order_id)
        return jsonify({"ok": True, "already_recorded": True})

    # Guardar el pago con los minutos
    payment = Payment(
        user_id=user_id,
        order_id=order_id,
        sku=sku,
        minutes=minutes,
        amount_usd=amount_usd,
        status="captured",
        raw_payload=data,
    )
    db.session.add(payment)
    db.session.commit()

    app.logger.info(
        "PayPal payment registrado: user=%s, +%s minutos (payment_id=%s)",
        user_id,
        minutes,
        payment.id,
    )

    return jsonify(
        {
            "ok": True,
            "user_id": user_id,
            "payment_id": payment.id,
            "credited_minutes": minutes,
        }
    )


# -----------------------------------------------------
# (Opcional) Ruta sencilla para probar que el BP está vivo
#  GET /paypal/ping
# -----------------------------------------------------
@bp.get("/ping")
def paypal_ping():
    return {"ok": True, "message": "paypal blueprint up"}
