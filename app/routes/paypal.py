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


def paypal_get_capture(capture_id: str) -> dict:
    """
    Si el id que nos llegó NO es un order_id sino un capture_id,
    esta ruta lo valida: GET /v2/payments/captures/{capture_id}
    """
    access_token = paypal_get_access_token()
    base_url = current_app.config["PAYPAL_BASE_URL"]
    r = requests.get(
        f"{base_url}/v2/payments/captures/{capture_id}",
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


@bp.get("/config")
def paypal_config():
    return jsonify(
        {
            "enabled": bool(current_app.config.get("PAYPAL_ENABLED")),
            "client_id": current_app.config.get("PAYPAL_CLIENT_ID"),
            "currency": (current_app.config.get("PAYPAL_CURRENCY", "USD") or "USD").upper(),
            "env": current_app.config.get("PAYPAL_ENV", "sandbox"),
        }
    )


@bp.post("/capture")
def paypal_capture():
    body = request.get_json(silent=True) or {}

    user_id = _get_user_id_from_request()
    paypal_id = str(body.get("order_id") or "").strip()  # puede ser OrderID o CaptureID
    sku = str(body.get("sku") or "").strip()
    minutes = int(body.get("minutes") or 0)
    amount = str(body.get("amount") or "").strip()

    if not user_id or not paypal_id or not sku or minutes <= 0 or not amount:
        return jsonify({"ok": False, "error": "missing_fields"}), 400

    # Idempotencia: si ya procesamos este paypal_id, no duplicar
    existing = Payment.query.filter_by(order_id=paypal_id).first()
    if existing and existing.status == "captured":
        return jsonify({"ok": True, "status": "already_captured"}), 200

    expected_currency = (current_app.config.get("PAYPAL_CURRENCY") or "USD").upper()

    # 1) Intentar validar como ORDER
    paid_value = None
    paid_currency = None
    verified_payload = None
    verified_kind = None

    try:
        order = paypal_get_order(paypal_id)
        verified_payload = order
        verified_kind = "order"

        status = (order.get("status") or "").upper()
        if status not in ("COMPLETED", "APPROVED"):
            return jsonify({"ok": False, "error": "order_not_completed", "status": status}), 400

        # Si está COMPLETED, normalmente tiene captures dentro
        try:
            pu = (order.get("purchase_units") or [])[0]
            captures = pu.get("payments", {}).get("captures", [])
            if captures:
                amt = captures[0]["amount"]
                paid_value = str(amt["value"])
                paid_currency = str(amt["currency_code"])
            else:
                # fallback: amount directo del purchase_unit
                amt = pu.get("amount", {})
                paid_value = str(amt.get("value", ""))
                paid_currency = str(amt.get("currency_code", ""))
        except Exception:
            current_app.logger.exception("Could not parse ORDER amount/currency")
            return jsonify({"ok": False, "error": "bad_order_shape"}), 400

    except Exception as e:
        # 2) Si falló como ORDER, intentar como CAPTURE
        current_app.logger.warning("PayPal order lookup failed, trying capture lookup: %s", e)
        try:
            cap = paypal_get_capture(paypal_id)
            verified_payload = cap
            verified_kind = "capture"

            status = (cap.get("status") or "").upper()
            if status != "COMPLETED":
                return jsonify({"ok": False, "error": "capture_not_completed", "status": status}), 400

            amt = cap.get("amount") or {}
            paid_value = str(amt.get("value", ""))
            paid_currency = str(amt.get("currency_code", ""))
        except Exception as e2:
            current_app.logger.exception("PayPal capture lookup also failed: %s", e2)
            return jsonify({"ok": False, "error": "paypal_lookup_failed"}), 502

    # Validar moneda y monto
    if not paid_currency or paid_currency.upper() != expected_currency:
        return jsonify({"ok": False, "error": "currency_mismatch", "paid": paid_currency}), 400

    # PayPal suele devolver 2 decimales; comparamos como string
    if paid_value != amount:
        return jsonify(
            {"ok": False, "error": "amount_mismatch", "paid": paid_value, "expected": amount}
        ), 400

    # Guardar Payment (status debe ser "captured" porque usage.py lo suma así)
    try:
        if not existing:
            p = Payment(
                user_id=str(user_id),
                order_id=paypal_id,
                sku=sku,
                minutes=minutes,
                amount_usd=float(amount),
                status="captured",
                raw_payload={"kind": verified_kind, "data": verified_payload},
            )
            db.session.add(p)
        else:
            existing.status = "captured"
            existing.sku = sku
            existing.minutes = minutes
            existing.amount_usd = float(amount)
            existing.raw_payload = {"kind": verified_kind, "data": verified_payload}

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Payment save failed: %s", e)
        return jsonify({"ok": False, "error": "db_failed"}), 500

    return jsonify({"ok": True, "credited_minutes": minutes}), 200


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

    # En esta versión dejamos el webhook como auditoría/backup.
    # La acreditación real está en /capture, que amarra user_id + pago.
    current_app.logger.info("PayPal webhook received: %s", event_type)
    return jsonify({"ok": True})
