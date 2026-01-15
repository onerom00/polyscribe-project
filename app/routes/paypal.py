# app/routes/paypal.py
from __future__ import annotations

import json
import os
import requests
from flask import Blueprint, current_app, request, jsonify

bp = Blueprint("paypal", __name__, url_prefix="/api/paypal")


def _paypal_headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def paypal_get_access_token() -> str:
    base_url = current_app.config["PAYPAL_BASE_URL"]
    cid = current_app.config["PAYPAL_CLIENT_ID"]
    secret = current_app.config["PAYPAL_CLIENT_SECRET"]

    r = requests.post(
        f"{base_url}/v1/oauth2/token",
        auth=(cid, secret),
        headers={"Accept": "application/json", "Accept-Language": "en_US"},
        data={"grant_type": "client_credentials"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def paypal_verify_webhook_signature(event_body: dict) -> bool:
    """
    Verifica firma del webhook usando PayPal API:
    POST /v1/notifications/verify-webhook-signature
    """
    webhook_id = current_app.config.get("PAYPAL_WEBHOOK_ID")
    if not webhook_id:
        current_app.logger.warning("PAYPAL_WEBHOOK_ID missing; skipping verification (NOT recommended).")
        return True  # puedes poner False si quieres forzar seguridad

    access_token = paypal_get_access_token()
    base_url = current_app.config["PAYPAL_BASE_URL"]

    transmission_id = request.headers.get("PAYPAL-TRANSMISSION-ID", "")
    transmission_time = request.headers.get("PAYPAL-TRANSMISSION-TIME", "")
    cert_url = request.headers.get("PAYPAL-CERT-URL", "")
    auth_algo = request.headers.get("PAYPAL-AUTH-ALGO", "")
    transmission_sig = request.headers.get("PAYPAL-TRANSMISSION-SIG", "")

    payload = {
        "auth_algo": auth_algo,
        "cert_url": cert_url,
        "transmission_id": transmission_id,
        "transmission_sig": transmission_sig,
        "transmission_time": transmission_time,
        "webhook_id": webhook_id,
        "webhook_event": event_body,
    }

    r = requests.post(
        f"{base_url}/v1/notifications/verify-webhook-signature",
        headers=_paypal_headers(access_token),
        data=json.dumps(payload),
        timeout=30,
    )
    r.raise_for_status()
    status = (r.json().get("verification_status") or "").upper()
    return status == "SUCCESS"


def plan_to_minutes(plan_id: str) -> int:
    """
    Mapea plan_id -> minutos.
    Ajusta según tus cards reales:
    Starter $9.99 -> 60
    Pro $19.99 -> 300
    Business $49.99 -> 1200
    """
    plan_id = (plan_id or "").strip()

    starter = current_app.config.get("PAYPAL_PLAN_STARTER_ID", "")
    pro = current_app.config.get("PAYPAL_PLAN_PRO_ID", "")
    business = current_app.config.get("PAYPAL_PLAN_BUSINESS_ID", "")

    if plan_id and plan_id == starter:
        return 60
    if plan_id and plan_id == pro:
        return 300
    if plan_id and plan_id == business:
        return 1200
    return 0


@bp.route("/webhook", methods=["POST"])
def paypal_webhook():
    event = request.get_json(silent=True) or {}
    event_type = event.get("event_type", "UNKNOWN")

    # 1) Verificar firma
    try:
        if not paypal_verify_webhook_signature(event):
            current_app.logger.warning("PayPal webhook signature verification FAILED")
            return jsonify({"ok": False, "error": "bad signature"}), 400
    except Exception as e:
        current_app.logger.exception("PayPal verification error: %s", e)
        return jsonify({"ok": False, "error": "verify error"}), 500

    # 2) Procesar eventos que dan minutos
    # Recomendado: usar ACTIVATED y/o PAYMENT.SALE.COMPLETED según tu flujo.
    if event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
        resource = event.get("resource") or {}
        subscription_id = resource.get("id")
        plan_id = resource.get("plan_id")

        minutes = plan_to_minutes(plan_id)

        # TODO: aquí debes asociar subscription al user (según tu modelo).
        # Normalmente se hace guardando user_id cuando creas la suscripción (custom_id / subscriber / metadata).
        # Por ahora: solo log.
        current_app.logger.info(
            "SUB ACTIVATED sub=%s plan=%s minutes=%s", subscription_id, plan_id, minutes
        )

        # Si ya tienes la tabla/ledger: aquí haces el crédito
        # credit_minutes(user_id, minutes, source="paypal", ref=subscription_id)

    elif event_type == "PAYMENT.SALE.COMPLETED":
        current_app.logger.info("PAYMENT COMPLETED event received")

    else:
        current_app.logger.info("PayPal event ignored: %s", event_type)

    return jsonify({"ok": True})
@bp.route("/config", methods=["GET"])
def paypal_config():
    return jsonify({
        "enabled": current_app.config.get("PAYPAL_ENABLED", False),
        "env": current_app.config.get("PAYPAL_ENV", "sandbox"),
        "currency": current_app.config.get("PAYPAL_CURRENCY", "USD"),
        "client_id": current_app.config.get("PAYPAL_CLIENT_ID"),
        "plans": {
            "starter": current_app.config.get("PAYPAL_PLAN_STARTER_ID"),
            "pro": current_app.config.get("PAYPAL_PLAN_PRO_ID"),
            "business": current_app.config.get("PAYPAL_PLAN_BUSINESS_ID"),
        }
    })
