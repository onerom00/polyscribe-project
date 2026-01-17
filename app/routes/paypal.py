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

    # Idempotencia
    existing = Payment.query.filter_by(order_id=order_id).first()
    if existing and existing.status == "captured":
        return jsonify({"ok": True, "status": "already_captured"}), 200

    # Validar con PayPal
    try:
        order = paypal_get_order(order_id)
    except Exception as e:
        current_app.logger.exception("PayPal get order failed: %s", e)
        return jsonify({"ok": False, "error": "paypal_lookup_failed"}), 502

    status = (order.get("status") or "").upper()
    if status != "COMPLETED":
        return jsonify({"ok": False, "error": "order_not_completed", "status": status}), 400

    # Validar monto/moneda
    try:
        pu = (order.get("purchase_units") or [])[0]

        # PayPal a veces devuelve captures aquí:
        captures = pu.get("payments", {}).get("captures", [])
        if not captures:
            return jsonify({"ok": False, "error": "no_capture_found"}), 400

        amt = captures[0]["amount"]
        paid_value = str(amt["value"])
        paid_currency = str(amt["currency_code"])
    except Exception
