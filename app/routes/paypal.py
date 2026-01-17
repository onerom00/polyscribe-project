# app/routes/paypal.py
from __future__ import annotations

import json
import requests
from flask import Blueprint, current_app, request, jsonify

from app.extensions import db
from app.models_payment import Payment

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


def paypal_get_order(order_id: str) -> dict:
    access_token = paypal_get_access_token()
    base_url = current_app.config["PAYPAL_BASE_URL"]

    r = requests.get(
        f"{base_url}/v2/checkout/orders/{order_id}",
        headers=_paypal_headers(access_token),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _get_user_id_from_request() -> str:
    # prioridad: header (dev login), luego json body
    uid = (request.headers.get("X-User-Id") or "").strip()
    if uid:
        return uid
    body = request.get_json(silent=True) or {}
    return str(body.get("user_id") or "").strip()


@bp.get("/config")
def paypal_config():
    # Lo usa static/js/payments.js para decidir si renderiza botones
    return jsonify(
        {
            "enabled": bool(current_app.config.get("PAYPAL_ENABLED", True)),
            "client_id": current_app.config.get("PAYPAL_CLIENT_ID"),
            "currency": current_app.config.get("PAYPAL_CURRENCY", "USD"),
            "env": current_app.config.get("PAYPAL_ENV", "live"),
        }
    )


@bp.post("/capture")
def paypal_capture():
    body = request.get_json(silent=True) or {}

    user_id = _get_user_id_from_request()
    order_id = str(body.get("order_id") or "").strip()
    sku = str(body.get("sku") or "").strip()
    minutes = int(body.get("minutes") or 0)
    amount = str(body.get("amount") or "").strip()

    if not user_id or not order_id or not sku or minutes <= 0 or not amount:
        return jsonify({"ok": False, "error": "missing_fields"}), 400

    # Idempotencia: si ya procesamos este order_id como captured, no volver a acreditar
    existing = Payment.query.filter_by(order_id=order_id).first()
    if existing and str(existing.status).lower() == "captured":
        return jsonify({"ok": True, "status": "already_captured"}), 200

    # Validar con PayPal (fuente de verdad)
    try:
        order = paypal_get_order(order_id)
    except Exception as e:
        current_app.logger.exception("PayPal get order failed: %s", e)
        return jsonify({"ok": False, "error": "paypal_lookup_failed"}), 502

    status = (order.get("status") or "").upper()
    if status != "COMPLETED":
        # a veces puedes recibir APPROVED si aún no capturó
        return jsonify({"ok": False, "error": "order_not_completed", "status": status}), 400

    # Validar monto/moneda (PayPal puede variar la forma)
    try:
        purchase_units = order.get("purchase_units") or []
        pu0 = purchase_units[0]

        # capturas típicas:
        captures = (
            pu0.get("payments", {}).get("captures", [])
            if isinstance(pu0.get("payments", {}), dict)
            else []
        )
        if not captures:
            # fallback: algunos casos traen "purchase_units[0].amount" pero es menos confiable
            return jsonify({"ok": False, "error": "no_capture_found"}), 400

        amt = captures[0].get("amount", {})
        paid_value = str(amt.get("value", "")).strip()
        paid_currency = str(amt.get("currency_code", "")).strip()
    except Exception as e:
        current_app.logger.exception("Could not parse PayPal order capture amount: %s", e)
        return jsonify({"ok": False, "error": "bad_order_shape"}), 400

    expected_currency = (current_app.config.get("PAYPAL_CURRENCY") or "USD").upper()
    if paid_currency.upper() != expected_currency:
        return jsonify(
            {"ok": False, "error": "currency_mismatch", "paid": paid_currency, "expected": expected_currency}
        ), 400

    # Comparación de monto como string (PayPal suele devolver con 2 decimales)
    if paid_value != amount:
        return jsonify(
            {"ok": False, "error": "amount_mismatch", "paid": paid_value, "expected": amount}
        ), 400

    # Guardar Payment como CAPTURED (porque usage.py suma Payment.status == "captured")
    try:
        if not existing:
            p = Payment(
                user_id=str(user_id),
                order_id=order_id,
                sku=sku,
                minutes=minutes,
                amount_usd=float(amount),
                status="captured",
                raw_payload=order,
            )
            db.session.add(p)
        else:
            existing.user_id = str(user_id)
            existing.sku = sku
            existing.minutes = minutes
            existing.amount_usd = float(amount)
            existing.status = "captured"
            existing.raw_payload = order

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Payment save failed: %s", e)
        return jsonify({"ok": False, "error": "payment_save_failed"}), 500

    return jsonify({"ok": True, "credited_minutes": minutes, "status": "captured"}), 200


def paypal_verify_webhook_signature(event_body: dict) -> bool:
    webhook_id = current_app.config.get("PAYPAL_WEBHOOK_ID")
    if not webhook_id:
        current_app.logger.warning("PAYPAL_WEBHOOK_ID missing; skipping verification (NOT recommended).")
        return True

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


@bp.route("/webhook", methods=["POST"])
def paypal_webhook():
    event = request.get_json(silent=True) or {}
    event_type = (event.get("event_type") or "UNKNOWN").upper()

    # Verificar firma
    try:
        if not paypal_verify_webhook_signature(event):
            current_app.logger.warning("PayPal webhook signature verification FAILED")
            return jsonify({"ok": False, "error": "bad_signature"}), 400
    except Exception as e:
        current_app.logger.exception("PayPal verification error: %s", e)
        return jsonify({"ok": False, "error": "verify_error"}), 500

    current_app.logger.info("PayPal webhook received: %s", event_type)
    return jsonify({"ok": True})
