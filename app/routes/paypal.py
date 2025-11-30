# app/routes/paypal.py
from __future__ import annotations

import logging
from typing import Dict, Any

import requests
from flask import Blueprint, current_app, request, jsonify, render_template

bp = Blueprint("paypal", __name__)

log = logging.getLogger(__name__)

# Intentamos importar una función opcional para acreditar minutos
try:
    from app.models_payment import credit_minutes as _credit_minutes
except Exception:  # noqa: BLE001
    _credit_minutes = None

# Definición de planes (deben coincidir con pricing.html)
PLANS: Dict[str, Dict[str, Any]] = {
    "starter": {
        "price": "9.00",
        "minutes": 60,
        "name": "PolyScribe Starter",
    },
    "pro": {
        "price": "29.00",
        "minutes": 300,
        "name": "PolyScribe Pro",
    },
    "business": {
        "price": "89.00",
        "minutes": 1200,
        "name": "PolyScribe Business",
    },
}


def _get_paypal_token() -> str:
    """Obtiene un access token de PayPal usando client_credentials."""
    base_url = current_app.config["PAYPAL_BASE_URL"]
    client_id = current_app.config["PAYPAL_CLIENT_ID"]
    client_secret = current_app.config["PAYPAL_CLIENT_SECRET"]

    if not client_id or not client_secret:
        raise RuntimeError("PayPal no está configurado correctamente.")

    resp = requests.post(
        f"{base_url}/v1/oauth2/token",
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
        timeout=15,
    )
    if not resp.ok:
        log.error("Error al obtener token de PayPal: %s - %s", resp.status_code, resp.text)
        raise RuntimeError("No se pudo obtener token de PayPal.")
    data = resp.json()
    return data["access_token"]


def _build_return_urls(user_id: str, plan: str) -> Dict[str, str]:
    """Arma las URLs de retorno/cancelación para el checkout."""
    app_base = current_app.config.get("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

    return {
        # Página de “gracias” dentro de la propia app
        "return_url": f"{app_base}/paypal/thanks?plan={plan}&user_id={user_id}",
        "cancel_url": f"{app_base}/pricing?paypal_cancel=1&plan={plan}",
    }


@bp.post("/api/paypal/subscribe")
def create_paypal_order():
    """
    Crea una orden de PayPal para el plan indicado y devuelve la approval_url.
    Espera JSON: { "plan": "starter" | "pro" | "business" }
    Usa el header X-User-Id para saber a qué usuario asociar la compra.
    """
    if not current_app.config.get("PAYPAL_ENABLED", False):
        return jsonify({"error": "PayPal no está habilitado."}), 400

    user_id = request.headers.get("X-User-Id")
    if not user_id:
        return jsonify({"error": "Falta el identificador de usuario (X-User-Id)."}), 400

    data = request.get_json(silent=True) or {}
    plan_key = (data.get("plan") or "").lower().strip()

    if plan_key not in PLANS:
        return jsonify({"error": "Plan inválido."}), 400

    plan = PLANS[plan_key]
    access_token = _get_paypal_token()

    amount_value = plan["price"]
    currency = current_app.config.get("PAYPAL_CURRENCY", "USD")
    return_urls = _build_return_urls(user_id=user_id, plan=plan_key)

    order_payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "amount": {
                    "currency_code": currency,
                    "value": amount_value,
                },
                "description": f"{plan['name']} ({plan['minutes']} min)",
                "custom_id": f"user:{user_id}|plan:{plan_key}",
            }
        ],
        "application_context": {
            "brand_name": "PolyScribe",
            "landing_page": "NO_PREFERENCE",
            "user_action": "PAY_NOW",
            "return_url": return_urls["return_url"],
            "cancel_url": return_urls["cancel_url"],
        },
    }

    base_url = current_app.config["PAYPAL_BASE_URL"]
    resp = requests.post(
        f"{base_url}/v2/checkout/orders",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json=order_payload,
        timeout=20,
    )

    if not resp.ok:
        log.error("Error al crear orden de PayPal: %s - %s", resp.status_code, resp.text)
        return jsonify({
            "error": "No se pudo crear la orden en PayPal.",
            "status": resp.status_code,
            "details": resp.text,
        }), 500

    order = resp.json()
    approval_url = None
    for link in order.get("links", []):
        if link.get("rel") == "approve":
            approval_url = link.get("href")
            break

    if not approval_url:
        log.error("No se encontró approval_url en la respuesta de PayPal: %s", order)
        return jsonify({"error": "PayPal no devolvió una URL de aprobación."}), 500

    return jsonify({"approval_url": approval_url})


@bp.post("/api/paypal/webhook")
def paypal_webhook():
    """
    Webhook de PayPal: recibe eventos como PAYMENT.CAPTURE.COMPLETED.
    En sandbox tenemos PAYPAL_SKIP_VERIFY=1, así que no verificamos firma.
    Aquí acreditamos minutos al usuario según el plan comprado, si existe
    la función credit_minutes() en models_payment.
    """
    skip_verify = current_app.config.get("PAYPAL_SKIP_VERIFY", False)
    event = request.get_json(force=True, silent=True) or {}

    if not skip_verify:
        # TODO: verificación real para producción (firma e ID del webhook).
        pass

    event_type = event.get("event_type")
    resource = event.get("resource", {})
    custom_id = resource.get("custom_id")

    log.info("Webhook PayPal: type=%s custom_id=%s payload=%s", event_type, custom_id, event)

    # custom_id tiene forma "user:<id>|plan:<plan>"
    if custom_id and event_type == "PAYMENT.CAPTURE.COMPLETED":
        try:
            parts = custom_id.split("|")
            data_map = {}
            for part in parts:
                if ":" in part:
                    k, v = part.split(":", 1)
                    data_map[k] = v
            user_id = data_map.get("user")
            plan_key = data_map.get("plan")

            if user_id and plan_key in PLANS:
                minutes = PLANS[plan_key]["minutes"]

                if _credit_minutes:
                    # Llama a tu función real de acreditación de minutos
                    _credit_minutes(
                        user_id=user_id,
                        minutes=minutes,
                        source="paypal",
                        plan_key=plan_key,
                        raw_event=event,
                    )
                    log.info(
                        "Se acreditaron %s minutos al usuario %s por plan %s vía credit_minutes().",
                        minutes,
                        user_id,
                        plan_key,
                    )
                else:
                    # Si aún no implementaste credit_minutes, al menos lo dejamos logueado
                    log.warning(
                        "No se encontró credit_minutes() en models_payment. "
                        "Minutos NO acreditados todavía. user=%s plan=%s minutes=%s",
                        user_id,
                        plan_key,
                        minutes,
                    )
        except Exception as exc:  # noqa: BLE001
            log.exception("Error procesando webhook PayPal: %s", exc)

    return jsonify({"status": "ok"})


@bp.get("/paypal/thanks")
def paypal_thanks():
    """
    Página de agradecimiento tras volver de PayPal (return_url).
    No acredita minutos; eso lo hace el webhook. Aquí sólo mostramos info.
    """
    plan_key = (request.args.get("plan") or "").lower().strip()
    user_id = request.args.get("user_id") or ""
    plan = PLANS.get(plan_key)

    return render_template(
        "paypal_thanks.html",
        plan_key=plan_key,
        plan=plan,
        user_id=user_id,
    )
