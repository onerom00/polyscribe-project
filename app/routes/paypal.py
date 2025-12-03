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


# -------------------------------------------------------------------
# BLUEPRINT 1: Rutas públicas de PayPal (/paypal/...)
# -------------------------------------------------------------------
bp = Blueprint("paypal", __name__, url_prefix="/paypal")


@bp.get("/thanks")
def paypal_thanks():
    """
    Página a la que redirige PayPal después del pago.
    La acreditación real de minutos se hace vía webhook o /api/paypal/capture.
    """
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
              Nota: la acreditación de minutos se realiza mediante el webhook de PayPal
              o la API interna. Si el pago se canceló o no se completó, es posible
              que no se acrediten minutos.
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
    """Cuando el usuario cancela el pago en PayPal."""
    return redirect("/pricing?cancel=1")


@bp.post("/webhook")
def paypal_webhook():
    """
    Endpoint de webhook de PayPal (configurado en el dashboard).

    Guarda el evento crudo en PaymentEvent. Luego, si quieres,
    aquí puedes procesar BILLING.SUBSCRIPTION.* o PAYMENT.SALE.COMPLETED.
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
# BLUEPRINT 2: API del frontend (/api/paypal/...)
# -------------------------------------------------------------------
api_bp = Blueprint("paypal_api", __name__, url_prefix="/api/paypal")


@api_bp.get("/config")
def paypal_config():
    """
    Devuelve la configuración mínima para el JS:
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
    Aquí registramos el pago y abonamos minutos al usuario.
    """
    data = request.get_json(force=True, silent=True) or {}

    order_id = data.get("order_id")
    sku = data.get("sku")  # starter_60 / pro_300 / biz_1200
    minutes = int(data.get("minutes", 0) or 0)
    amount = float(data.get("amount", 0) or 0.0)
    user_id = data.get("user_id") or request.args.get("user_id") or "guest"

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

        # 2) Registrar en UsageLedger los minutos acreditados
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

    return jsonify({"ok": True}), 200


@api_bp.post("/subscribe")
def paypal_subscribe_legacy():
    """
    Endpoint legacy para que /api/paypal/subscribe no devuelva 404.
    Ahora el flujo correcto usa /api/paypal/capture.
    """
    return (
        jsonify(
            {
                "error": "Este endpoint ha sido reemplazado por /api/paypal/capture. "
                "Actualiza tu JavaScript.",
            }
        ),
        410,
    )
