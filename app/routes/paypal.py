# app/routes/paypal.py
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, redirect, request
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models import UsageLedger
from app.models_payment import Payment, PaymentEvent
from app.paypal_sdk import PayPalSDK

# -----------------------------------------------------------
# BLUEPRINT 1: Rutas públicas (/paypal/...)
#   - thanks
#   - cancel
#   - webhook
# -----------------------------------------------------------
bp = Blueprint("paypal", __name__, url_prefix="/paypal")


@bp.get("/thanks")
def paypal_thanks():
    """Página simple de agradecimiento después del pago (opcional)."""
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
              Nota: la acreditación real de minutos se realiza mediante el webhook de PayPal
              y el registro en la base de datos.
            </p>
            <p>
              <a href="/?user_id={user_id}">Ir a transcribir</a> ·
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
    """Cuando el usuario cancela el pago en PayPal."""
    return redirect("/pricing?cancel=1")


@bp.post("/webhook")
def paypal_webhook():
    """
    Webhook oficial de PayPal (configurado en el dashboard Sandbox).
    De momento solo registramos el evento.
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


# -----------------------------------------------------------
# BLUEPRINT 2: API para el frontend (/api/paypal/...)
#   - /config   -> el JS pide client_id para cargar el SDK
#   - /capture  -> el JS nos notifica que el pago fue capturado
#   - /subscribe (legacy) -> devuelve 410 para llamadas viejas
# -----------------------------------------------------------
api_bp = Blueprint("paypal_api", __name__, url_prefix="/api/paypal")


@api_bp.get("/config")
def paypal_config():
    """
    Devuelve la configuración mínima para que el JS cargue el SDK:
      { enabled, client_id, currency, env }
    """
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
    El JS ya hizo actions.order.capture() en el navegador.
    Aquí sólo registramos el pago y abonamos minutos al usuario.
    """
    data = request.get_json(silent=True) or {}

    order_id = data.get("order_id")
    sku = data.get("sku")                 # starter_60 / pro_300 / biz_1200
    minutes = int(data.get("minutes", 0) or 0)
    amount = float(data.get("amount", 0) or 0.0)

    # user_id opcional: puede venir por query o en el JSON
    user_id = request.args.get("user_id") or data.get("user_id") or "guest"

    if not order_id or minutes <= 0 or amount <= 0:
        return jsonify({"error": "Datos de pago incompletos"}), 400

    try:
        # 1) Registrar el pago
        payment = Payment(
            user_id=user_id,
            plan_id=sku,
            order_id=order_id,
            amount=amount,
            status="captured",
        )
        db.session.add(payment)

        # 2) Registrar en el ledger los minutos abonados
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
        return jsonify({"error": f"DB error: {exc}"}), 500

    return jsonify({"ok": True})


@api_bp.post("/subscribe")
def paypal_subscribe_legacy():
    """
    Endpoint de compatibilidad: si algún JS viejo llama a /api/paypal/subscribe
    devolvemos 410 en lugar de 404, con mensaje claro.
    """
    return (
        jsonify(
            {
                "error": (
                    "Este endpoint ha sido reemplazado por /api/paypal/capture. "
                    "Actualiza el JavaScript del frontend."
                )
            }
        ),
        410,
    )
