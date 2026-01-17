# app/routes/paypal_api.py
from __future__ import annotations

from flask import Blueprint, current_app, request, jsonify
from app.paypal_sdk import PayPalSDK

bp = Blueprint("paypal_api", __name__, url_prefix="/api/paypal")


@bp.post("/subscribe")
def subscribe():
    """
    Endpoint llamado por la página de /pricing.
    Crea una suscripción en PayPal y devuelve la URL de aprobación.
    """
    if not current_app.config.get("PAYPAL_ENABLED", False):
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "PAYPAL_DISABLED",
                    "message": "PayPal no está configurado en el servidor",
                }
            ),
            400,
        )

    data = request.get_json() or {}
    # Por ahora solo manejamos el plan "starter"
    plan_code = data.get("plan", "starter")
    user_id = data.get("user_id") or "guest"

    # ID del plan configurado en Render (PAYPAL_PLAN_STARTER_ID)
    plan_id = current_app.config.get("PAYPAL_PLAN_STARTER_ID")
    if not plan_id:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "MISSING_PLAN_ID",
                    "message": "Falta la variable PAYPAL_PLAN_STARTER_ID en Render",
                }
            ),
            500,
        )

    base_url = current_app.config.get("APP_BASE_URL", "").rstrip("/") or "http://127.0.0.1:8000"
    return_url = f"{base_url}/paypal/thanks?plan={plan_code}&user_id={user_id}"
    cancel_url = f"{base_url}/paypal/cancel?plan={plan_code}&user_id={user_id}"

    sdk = PayPalSDK()

    try:
        # Este método debe existir en tu app/paypal_sdk.py
        subscription = sdk.create_subscription(
            plan_id=plan_id,
            return_url=return_url,
            cancel_url=cancel_url,
            custom_id=user_id,
        )
    except Exception as e:
        current_app.logger.exception("Error al crear suscripción PayPal")
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "PAYPAL_API_ERROR",
                    "message": "Error al conectarse con PayPal",
                    "detail": str(e),
                }
            ),
            500,
        )

    approve_url = None
    for link in subscription.get("links", []):
        if link.get("rel") == "approve":
            approve_url = link.get("href")
            break

    if not approve_url:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "MISSING_APPROVE_URL",
                    "message": "No se encontró el enlace de aprobación en la respuesta de PayPal",
                    "raw": subscription,
                }
            ),
            500,
        )

    # Devolvemos lo mínimo que necesita el frontend
    return jsonify(
        {
            "ok": True,
            "subscription_id": subscription.get("id"),
            "approve_url": approve_url,
        }
    )
