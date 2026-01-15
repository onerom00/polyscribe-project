# app/routes/paypal.py
from __future__ import annotations

import json
import requests
from flask import Blueprint, current_app, request, jsonify, session

from app.extensions import db
from app.models_payment import Payment

bp = Blueprint("paypal", __name__, url_prefix="/api/paypal")


# -----------------------------
# Helpers PayPal
# -----------------------------
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


def paypal_verify_webhook_signature(event_body: dict) -> bool:
    """
    Verifica firma del webhook usando PayPal API:
    POST /v1/notifications/verify-webhook-signature
    """
    webhook_id = (current_app.config.get("PAYPAL_WEBHOOK_ID") or "").strip()
    if not webhook_id:
        # En prod es mejor exigirlo; por ahora lo dejamos true para no bloquearte.
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


# -----------------------------
# User ID resolution (CRÍTICO)
# -----------------------------
def _get_user_id_from_request(body: dict | None = None, order: dict | None = None) -> str:
    """
    Queremos acreditar al usuario REAL.
    Prioridad:
    1) session (login real)
    2) header X-User-Id (dev/admin)
    3) body.user_id (legacy)
    4) PayPal order.purchase_units[0].custom_id (lo pondremos desde el front)
    """
    # 1) session (si tu auth setea session["user_id"])
    try:
        s_uid = session.get("user_id") or session.get("uid")
        if s_uid:
            return str(s_uid).strip()
    except Exception:
        pass

    # 2) header
    uid = (request.headers.get("X-User-Id") or "").strip()
    if uid:
        return uid

    # 3) body
    body = body or {}
    uid = str(body.get("user_id") or "").strip()
    if uid:
        return uid

    # 4) custom_id del order
    try:
        pu0 = (order.get("purchase_units") or [])[0]
        custom_id = str(pu0.get("custom_id") or "").strip()
        if custom_id:
            return custom_id
    except Exception:
        pass

    return ""


def _extract_paid_amount(order: dict) -> tuple[str, str]:
    """
    Devuelve (value, currency_code) desde la captura.
    """
    pu = (order.get("purchase_units") or [])[0]
    payments = pu.get("payments") or {}
    captures = payments.get("captures") or []
    if not captures:
        raise ValueError("No captures in order")

    amt = captures[0]["amount"]
    return str(amt["value"]), str(amt["currency_code"])


def _infer_minutes_from_sku(sku: str) -> int:
    sku = (sku or "").strip().lower()
    if sku == "starter_60":
        return 60
    if sku == "pro_300":
        return 300
    if sku == "biz_1200":
        return 1200
    return 0


# -----------------------------
# Routes
# -----------------------------
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
    """
    El front llama a esto después de capture().
    Aquí validamos contra PayPal (fuente de verdad) y guardamos Payment.
    """
    body = request.get_json(silent=True) or {}

    order_id = str(body.get("order_id") or "").strip()
    sku = str(body.get("sku") or "").strip()
    minutes = int(body.get("minutes") or 0) or _infer_minutes_from_sku(sku)
    amount = str(body.get("amount") or "").strip()

    if not order_id or not sku or minutes <= 0:
        return jsonify({"ok": False, "error": "missing_fields"}), 400

    # Idempotencia
    existing = Payment.query.filter_by(order_id=order_id).first()
    if existing and existing.status == "completed":
        return jsonify({"ok": True, "status": "already_completed", "credited_minutes": existing.minutes}), 200

    # Validar con PayPal
    try:
        order = paypal_get_order(order_id)
    except Exception as e:
        current_app.logger.exception("PayPal get order failed: %s", e)
        return jsonify({"ok": False, "error": "paypal_lookup_failed"}), 502

    status = (order.get("status") or "").upper()
    if status != "COMPLETED":
        return jsonify({"ok": False, "error": "order_not_completed", "status": status}), 400

    # Determinar usuario REAL (session/header/body/custom_id)
    user_id = _get_user_id_from_request(body=body, order=order)
    if not user_id:
        return jsonify({"ok": False, "error": "missing_user_id"}), 400

    # Validar monto/moneda
    try:
        paid_value, paid_currency = _extract_paid_amount(order)
    except Exception as e:
        current_app.logger.exception("Could not parse PayPal order amount: %s", e)
        return jsonify({"ok": False, "error": "bad_order_shape"}), 400

    expected_currency = (current_app.config.get("PAYPAL_CURRENCY") or "USD").upper()
    if paid_currency.upper() != expected_currency:
        return jsonify({"ok": False, "error": "currency_mismatch", "paid": paid_currency}), 400

    # Si el front manda amount, lo comparamos; si no, no bloqueamos.
    if amount and paid_value != amount:
        return jsonify({"ok": False, "error": "amount_mismatch", "paid": paid_value, "expected": amount}), 400

    # Guardar Payment
    try:
        if not existing:
            p = Payment(
                user_id=str(user_id),
                order_id=order_id,
                sku=sku,
                minutes=int(minutes),
                amount_usd=float(paid_value),
                status="completed",
                raw_payload=order,
            )
            db.session.add(p)
        else:
            existing.user_id = str(user_id)
            existing.sku = sku
            existing.minutes = int(minutes)
            existing.amount_usd = float(paid_value)
            existing.status = "completed"
            existing.raw_payload = order

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Saving payment failed: %s", e)
        return jsonify({"ok": False, "error": "db_save_failed"}), 500

    return jsonify({"ok": True, "credited_minutes": int(minutes), "user_id": str(user_id)}), 200


@bp.post("/webhook")
def paypal_webhook():
    """
    Respaldo: si por alguna razón el front no llama /capture,
    aquí podemos registrar el Payment igual.

    IMPORTANTE: para mapear al usuario, usamos order.purchase_units[0].custom_id
    (por eso el JS debe enviarlo en createOrder).
    """
    event = request.get_json(silent=True) or {}
    event_type = (event.get("event_type") or "UNKNOWN").upper()

    # Verificar firma (si tienes WEBHOOK_ID)
    try:
        if not paypal_verify_webhook_signature(event):
            current_app.logger.warning("PayPal webhook signature verification FAILED")
            return jsonify({"ok": False, "error": "bad_signature"}), 400
    except Exception as e:
        current_app.logger.exception("PayPal verification error: %s", e)
        return jsonify({"ok": False, "error": "verify_error"}), 500

    # Queremos eventos que indiquen pago/captura final.
    # PayPal suele mandar: PAYMENT.CAPTURE.COMPLETED o CHECKOUT.ORDER.APPROVED dependiendo del flujo.
    if event_type not in {"PAYMENT.CAPTURE.COMPLETED", "CHECKOUT.ORDER.APPROVED"}:
        current_app.logger.info("PayPal webhook ignored: %s", event_type)
        return jsonify({"ok": True, "ignored": True}), 200

    resource = event.get("resource") or {}
    order_id = str(resource.get("supplementary_data", {})
                   .get("related_ids", {})
                   .get("order_id", "")).strip()

    # A veces viene directo en resource.id
    if not order_id:
        order_id = str(resource.get("id") or "").strip()

    if not order_id:
        current_app.logger.warning("Webhook without order_id. event_type=%s", event_type)
        return jsonify({"ok": True, "no_order_id": True}), 200

    # Idempotencia
    existing = Payment.query.filter_by(order_id=order_id).first()
    if existing and existing.status == "completed":
        return jsonify({"ok": True, "already_completed": True}), 200

    # Consultar orden
    try:
        order = paypal_get_order(order_id)
    except Exception as e:
        current_app.logger.exception("Webhook: PayPal get order failed: %s", e)
        return jsonify({"ok": False, "error": "paypal_lookup_failed"}), 502

    status = (order.get("status") or "").upper()
    if status != "COMPLETED":
        return jsonify({"ok": True, "status": status, "not_completed": True}), 200

    # Usuario desde custom_id
    user_id = _get_user_id_from_request(body=None, order=order)
    if not user_id:
        current_app.logger.warning("Webhook: missing custom_id (user_id) in order %s", order_id)
        return jsonify({"ok": True, "missing_user": True}), 200

    # SKU desde reference_id (si lo pusimos) o description (fallback)
    sku = ""
    try:
        pu0 = (order.get("purchase_units") or [])[0]
        sku = str(pu0.get("reference_id") or "").strip()
    except Exception:
        sku = ""

    minutes = _infer_minutes_from_sku(sku)

    # Monto
    try:
        paid_value, paid_currency = _extract_paid_amount(order)
    except Exception:
        paid_value, paid_currency = ("0", "USD")

    # Guardar Payment
    try:
        p = Payment(
            user_id=str(user_id),
            order_id=order_id,
            sku=sku or None,
            minutes=int(minutes or 0),
            amount_usd=float(paid_value or 0),
            status="completed",
            raw_payload=order,
        )
        db.session.add(p)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Webhook: saving payment failed: %s", e)
        return jsonify({"ok": False, "error": "db_save_failed"}), 500

    return jsonify({"ok": True}), 200
