# app/routes/paypal.py
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

import requests
from flask import Blueprint, current_app, request, jsonify

from app import db
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
    uid = (request.headers.get("X-User-Id") or "").strip()
    if uid:
        return uid
    body = request.get_json(silent=True) or {}
    return str(body.get("user_id") or "").strip()


def _money_eq(a: str, b: str) -> bool:
    """Compara montos con tolerancia a formato."""
    try:
        da = Decimal(str(a))
        dbb = Decimal(str(b))
    except InvalidOperation:
        return False
    # tolerancia exacta a centavos
    return da.quantize(Decimal("0.01")) == dbb.quantize(Decimal("0.01"))


@bp.get("/config")
def paypal_config():
    return jsonify(
        {
            "enabled": bool(current_app.config.get("PAYPAL_ENABLED")),
            "client_id": current_app.config.get("PAYPAL_CLIENT_ID"),
            "currency": current_app.config.get("PAYPAL_CURRENCY", "USD"),
            "env": current_app.config.get("PAYPAL_ENV", "sandbox"),
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

    # Idempotencia: si ya procesamos este order_id, no volver a acreditar
    existing = Payment.query.filter_by(order_id=order_id).first()
    if existing and (existing.status in ("captured", "completed")):
        return jsonify({"ok": True, "status": "already_captured", "credited_minutes": int(existing.minutes or 0)}), 200

    # Validar con PayPal
    try:
        order = paypal_get_order(order_id)
    except Exception as e:
        current_app.logger.exception("PayPal get order failed: %s", e)
        return jsonify({"ok": False, "error": "paypal_lookup_failed"}), 502

    status = (order.get("status") or "").upper()
    if status != "COMPLETED":
        return jsonify({"ok": False, "error": "order_not_completed", "status": status}), 400

    # Leer monto y moneda desde capture
    try:
        pu = (order.get("purchase_units") or [])[0]
        cap = pu["payments"]["captures"][0]
        amt = cap["amount"]
        paid_value = str(amt["value"])
        paid_currency = str(amt["currency_code"])
    except Exception:
        current_app.logger.exception("Could not parse PayPal order capture amount")
        return jsonify({"ok": False, "error": "bad_order_shape"}), 400

    expected_currency = (current_app.config.get("PAYPAL_CURRENCY") or "USD").upper()
    if paid_currency.upper() != expected_currency:
        return jsonify({"ok": False, "error": "currency_mismatch", "paid": paid_currency, "expected": expected_currency}), 400

    if not _money_eq(paid_value, amount):
        return jsonify({"ok": False, "error": "amount_mismatch", "paid": paid_value, "expected": amount}), 400

    # Guardar Payment (esto es lo que usa /api/usage/balance para sumar minutos)
    try:
        if not existing:
            p = Payment(
                user_id=str(user_id),
                order_id=order_id,
                sku=sku,
                minutes=minutes,
                amount_usd=float(Decimal(amount).quantize(Decimal("0.01"))),
                status="captured",
                raw_payload=order,
            )
            db.session.add(p)
        else:
            existing.user_id = str(user_id)
            existing.status = "captured"
            existing.sku = sku
            existing.minutes = minutes
            existing.amount_usd = float(Decimal(amount).quantize(Decimal("0.01")))
            existing.raw_payload = order

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Payment save failed: %s", e)
        return jsonify({"ok": False, "error": "credit_failed"}), 500

    return jsonify({"ok": True, "credited_minutes": minutes, "user_id": user_id}), 200


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

    try:
        if not paypal_verify_webhook_signature(event):
            current_app.logger.warning("PayPal webhook signature verification FAILED")
            return jsonify({"ok": False, "error": "bad signature"}), 400
    except Exception as e:
        current_app.logger.exception("PayPal verification error: %s", e)
        return jsonify({"ok": False, "error": "verify error"}), 500

    current_app.logger.info("PayPal webhook received: %s", event_type)
    return jsonify({"ok": True})
