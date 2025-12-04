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
from app.paypal_sdk import PayPalSDK

# ===============================================================
# BLUEPRINT 1: Rutas públicas /paypal/...
# ===============================================================
bp = Blueprint("paypal", __name__, url_prefix="/paypal")


@bp.get("/thanks")
def paypal_thanks():
    """
    Página a la que redirige PayPal después del pago.
    La acreditación real de minutos se hace vía webhook o capture.
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
            <p>Has adquirido tu plan PolyScribe: <strong>{plan}</strong>.</p>
            <p>El saldo se asociará al usuario: <strong>{user_id}</strong>.</p>
            <p style="max-width:600px;margin:1rem auto;font-size:0.9rem">
              Nota: la acreditación de minutos se realiza mediante el webhook
              de PayPal o el endpoint /api/paypal/capture.
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

    Guarda el evento crudo en PaymentEvent. Más adelante,
    si quieres, puedes procesar aquí los minutos.
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


# ===============================================================
# BLUEPRINT 2: API /api/paypal/... para el frontend
# ===============================================================
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
    Flujo "nuevo": el JS hace actions.order.capture() en el navegador
    y nos envía aquí el resultado para abonar minutos al usuario.
    """
    data = request.get_json(silent=True) or {}

    order_id = data.get("order_id")
    sku = data.get("sku")              # starter_60 / pro_300 / biz_1200
    minutes = int(data.get("minutes", 0) or 0)
    amount = float(data.get("amount", 0) or 0.0)
    user_id = data.get("user_id") or request.args.get("user_id") or "guest"

    if not order_id or minutes <= 0 or amount <= 0:
        return jsonify({"error": "Datos de pago incompletos"}), 400

    try:
        # 1) Guardar registro de pago
        payment = Payment(
            user_id=user_id,
            plan_id=sku,
            order_id=order_id,
            amount=amount,
            currency=current_app.config.get("PAYPAL_CURRENCY", "USD"),
            status="captured",
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
        return jsonify({"error": f"DB error: {exc}"}), 500

    return jsonify({"ok": True}), 200


@api_bp.post("/subscribe")
def paypal_subscribe():
    """
    Flujo "legacy": usado por tu HTML/JS actual.
    Crea una orden en PayPal y devuelve approve_url para redirigir al usuario.

    Esto es lo que elimina el error 410 que ves en la consola.
    """
    if not current_app.config.get("PAYPAL_ENABLED"):
        return jsonify({"error": "PayPal no está configurado"}), 400

    data = request.get_json(silent=True) or {}

    # Lo que típicamente envía tu JS antiguo:
    # { plan_id, amount, user_id }
    plan_id = data.get("plan_id") or data.get("plan_code") or "starter"
    amount = float(data.get("amount", 0) or 0.0)
    user_id = data.get("user_id") or "guest"

    if amount <= 0:
        return jsonify({"error": "Monto inválido"}), 400

    sdk = PayPalSDK()
    try:
        order = sdk.create_order(amount=amount, plan_id=plan_id)
    except Exception as exc:
        current_app.logger.exception("Error creando orden PayPal: %s", exc)
        return jsonify({"error": "No se pudo crear la orden en PayPal"}), 500

    # Registrar creación del pago
    try:
        pay = Payment(
            user_id=user_id,
            plan_id=plan_id,
            order_id=order.get("id"),
            amount=amount,
            currency=current_app.config.get("PAYPAL_CURRENCY", "USD"),
            status="created",
        )
        db.session.add(pay)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()

    approve_url = None
    for link in order.get("links", []):
        if link.get("rel") == "approve":
            approve_url = link.get("href")
            break

    if not approve_url:
        return jsonify({"error": "No se recibió URL de aprobación de PayPal"}), 500

    return jsonify(
        {
            "order_id": order.get("id"),
            "approve_url": approve_url,
        }
    ), 200
