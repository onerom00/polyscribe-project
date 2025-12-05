# app/routes/paypal.py
from __future__ import annotations

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    request,
)
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models import UsageLedger
from app.models_payment import Payment, PaymentEvent
from app.paypal_sdk import PayPalSDK  # si en algún momento quieres verificar órdenes


# -------------------------------------------------------------------
# BLUEPRINT 1: Rutas "públicas" de PayPal (/paypal/...)
# -------------------------------------------------------------------
bp = Blueprint("paypal", __name__, url_prefix="/paypal")


@bp.get("/thanks")
def paypal_thanks():
    plan = request.args.get("plan", "starter")
    user_id = request.args.get("user_id", "guest")

    return (
        f"""
        <!doctype html>
        <html lang="es">
        <head>
            <meta charset="utf-8">
            <title>Pago exitoso</title>
        </head>
        <body style="font-family: system-ui; text-align: center; margin-top: 3rem;">
            <h1>✔ Pago recibido</h1>
            <p>Has adquirido tu plan PolyScribe ({plan}).</p>
            <p>El saldo se asociará al usuario: <strong>{user_id}</strong>.</p>
            <p style="max-width:600px;margin:1rem auto;font-size:0.9rem">
              Nota: la acreditación de minutos se realiza inmediatamente
              después de confirmar el pago.
            </p>
            <p>
              <a href="/?user_id={user_id}">Ir a transcribir</a> |
              <a href="/history?user_id={user_id}">Ver historial</a>
            </p>
        </body>
        </html>
        """,
        200,
        {"Content-Type": "text/html; charset=utf-8"},
    )


@bp.get("/cancel")
def paypal_cancel():
    return redirect("/pricing?cancel=1")


@bp.post("/webhook")
def paypal_webhook():
    """
    Guarda el evento crudo de PayPal (sin lógica compleja).
    """
    event = request.get_json(silent=True) or {}
    event_type = event.get("event_type", "unknown")

    try:
        db.session.add(
            PaymentEvent(
                event_type=event_type,
                raw_json=event,
            )
        )
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()

    return jsonify({"status": "ok"}), 200


# -------------------------------------------------------------------
# BLUEPRINT 2: API usada por el frontend (/api/paypal/...)
# -------------------------------------------------------------------
api_bp = Blueprint("paypal_api", __name__, url_prefix="/api/paypal")


@api_bp.get("/config")
def paypal_config():
    cfg = current_app.config
    if not cfg.get("PAYPAL_ENABLED"):
        return jsonify({"enabled": False})

    return jsonify(
        {
            "enabled": True,
            "client_id": cfg.get("PAYPAL_CLIENT_ID"),
            "currency": cfg.get("PAYPAL_CURRENCY", "USD"),
            "env": cfg.get("PAYPAL_ENV", "sandbox"),
        }
    )


@api_bp.post("/capture")
def paypal_capture():
    """
    Recibe del frontend:
      { order_id, sku, minutes, amount, user_id? }

    - Registra el pago en la tabla payments.
    - Abona minutos en UsageLedger.
    """
    data = request.get_json(silent=True) or {}

    order_id = data.get("order_id")
    sku = data.get("sku")  # ej: starter_60 / pro_300 / biz_1200
    minutes = int(data.get("minutes", 0) or 0)
    amount = float(data.get("amount", 0) or 0.0)
    user_id = data.get("user_id") or request.args.get("user_id") or "guest"

    if not order_id or minutes <= 0 or amount <= 0:
        return jsonify({"error": "Datos de pago incompletos"}), 400

    try:
        # 1) Registrar pago
        payment = Payment(
            user_id=user_id,
            plan_code=sku,  # columna existente en el modelo
            order_id=order_id,
            amount=amount,
            currency=current_app.config.get("PAYPAL_CURRENCY", "USD"),
            status="captured",
            minutes=minutes,
        )
        db.session.add(payment)

        # 2) Abonar minutos al ledger
        ledger = UsageLedger(
            user_id=user_id,
            delta_minutes=minutes,
            reason="paypal_capture",
            meta={
                "order_id": order_id,
                "sku": sku,
                "amount": amount,
            },
        )
        db.session.add(ledger)

        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.exception("paypal_capture DB error: %s", exc)
        return jsonify({"error": "DB error"}), 500

    return jsonify({"ok": True})


@api_bp.post("/subscribe")
def paypal_subscribe_legacy():
    """
    Endpoint de compatibilidad. Si algún JS viejo lo llama,
    respondemos con 410 para indicar que use /capture.
    """
    return (
        jsonify(
            {
                "error": "Este endpoint ha sido reemplazado por /api/paypal/capture."
            }
        ),
        410,
    )
