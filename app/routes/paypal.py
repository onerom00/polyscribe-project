# app/routes/paypal.py
from __future__ import annotations

import base64
import json
from typing import Dict, Any, Optional, Tuple

import requests
from flask import Blueprint, current_app, jsonify, request

from app import db
from app.models_payment import Payment

# ✅ Mantener ambos Blueprints porque app/__init__.py los importa
bp = Blueprint("paypal_pages", __name__, url_prefix="/paypal")
api_bp = Blueprint("paypal_api", __name__, url_prefix="/api/paypal")


# -----------------------------
# Helper: user_id consistente
# -----------------------------
def _get_user_id() -> str:
    uid = request.headers.get("X-User-Id") or request.args.get("user_id")
    if not uid:
        data = request.get_json(silent=True) or {}
        uid = data.get("user_id")
    return (uid or "guest").strip()


def _is_guest(uid: str) -> bool:
    u = (uid or "").strip().lower()
    return (
        not u
        or u == "guest"
        or u.startswith("guest-")
        or u == "id-guest"
        or u.startswith("id-guest-")
    )


def _require_login_or_401(user_id: str):
    """
    ✅ 1) Ocultar/bloquear guest en producción.
    El frontend (payments.js) ya maneja login_required.
    """
    # Puedes controlar esto por config si quieres:
    # PAYPAL_REQUIRE_LOGIN=True por defecto
    require_login = bool(current_app.config.get("PAYPAL_REQUIRE_LOGIN", True))
    if require_login and _is_guest(user_id):
        return jsonify({"error": "login_required"}), 401
    return None


# -----------------------------
# Planes PREPAGO (verdad del server)
# -----------------------------
PLANS = {
    "starter": {"sku": "starter_60", "minutes": 60, "price": "9.99"},
    "pro": {"sku": "pro_300", "minutes": 300, "price": "19.99"},
    "business": {"sku": "biz_1200", "minutes": 1200, "price": "49.99"},
}


def _paypal_base_url() -> str:
    # ✅ evita el %0a y otros espacios raros
    base_url = (current_app.config.get("PAYPAL_BASE_URL") or "").strip()
    # por si hubiese whitespace interno (muy raro), lo limpiamos
    base_url = "".join(base_url.split())
    return base_url.rstrip("/")


def _paypal_client_id() -> str:
    return (current_app.config.get("PAYPAL_CLIENT_ID") or "").strip()


def _paypal_client_secret() -> str:
    return (current_app.config.get("PAYPAL_CLIENT_SECRET") or "").strip()


def _paypal_currency() -> str:
    return (current_app.config.get("PAYPAL_CURRENCY") or "USD").strip().upper()


def _paypal_get_access_token() -> str:
    base_url = _paypal_base_url()
    client_id = _paypal_client_id()
    client_secret = _paypal_client_secret()

    if not base_url:
        raise RuntimeError("PAYPAL_BASE_URL missing")
    if not client_id or not client_secret:
        raise RuntimeError("PAYPAL_CLIENT_ID/SECRET missing")

    token = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")

    r = requests.post(
        f"{base_url}/v1/oauth2/token",
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "client_credentials"},
        timeout=20,
    )

    if r.status_code != 200:
        current_app.logger.error("PAYPAL_TOKEN_ERROR %s %s", r.status_code, r.text)
        raise RuntimeError("paypal_token_failed")

    return (r.json() or {}).get("access_token") or ""


def _paypal_headers(access_token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def _find_plan_by_amount(value: str) -> Optional[str]:
    v = str(value or "").strip()
    for k, p in PLANS.items():
        if str(p["price"]) == v:
            return k
    return None


def _extract_capture_info(cap: Dict[str, Any]) -> Tuple[str, str, str]:
    """
    Returns (capture_id, paid_value, paid_currency)
    """
    pu = (cap.get("purchase_units") or [{}])[0] or {}
    payments = pu.get("payments", {}) or {}
    captures = payments.get("captures", []) or []
    cap0 = captures[0] if captures else {}

    capture_id = str(cap0.get("id") or "").strip()

    amount = cap0.get("amount", {}) or {}
    paid_value = str(amount.get("value") or "").strip()
    paid_currency = str(amount.get("currency_code") or "").strip().upper()

    return capture_id, paid_value, paid_currency


def _extract_custom_id(cap: Dict[str, Any]) -> str:
    pu = (cap.get("purchase_units") or [{}])[0] or {}
    return str(pu.get("custom_id") or "").strip()


# -----------------------------------------------------
# (Opcional) ping para probar blueprint
# GET /paypal/ping
# -----------------------------------------------------
@bp.get("/ping")
def paypal_ping():
    return {"ok": True, "message": "paypal blueprint up"}


# -----------------------------------------------------
# API: CONFIG
# -----------------------------------------------------
@api_bp.get("/config")
def paypal_config():
    if not current_app.config.get("PAYPAL_ENABLED", False):
        return jsonify({"enabled": False}), 200

    return jsonify(
        {
            "enabled": True,
            "client_id": current_app.config.get("PAYPAL_CLIENT_ID"),
            "currency": _paypal_currency(),
            "env": current_app.config.get("PAYPAL_ENV", "live"),
        }
    )


# -----------------------------------------------------
# API: CREATE ORDER (server-side)
# POST /api/paypal/create-order
# Body: { plan: "starter" | "pro" | "business" }
# -----------------------------------------------------
@api_bp.post("/create-order")
def paypal_create_order():
    if not current_app.config.get("PAYPAL_ENABLED", False):
        return jsonify({"error": "PayPal no está habilitado en el servidor."}), 400

    data: Dict[str, Any] = request.get_json(silent=True) or {}
    plan_key = (data.get("plan") or "").strip().lower()

    if plan_key not in PLANS:
        return jsonify({"error": "Plan inválido."}), 400

    user_id = _get_user_id()

    # ✅ 1) Bloquear guest
    blocked = _require_login_or_401(user_id)
    if blocked:
        return blocked

    plan = PLANS[plan_key]

    try:
        access_token = _paypal_get_access_token()
        base_url = _paypal_base_url()

        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": plan["sku"],
                    "description": f"{plan['minutes']} minutos PolyScribe (prepago)",
                    "amount": {"currency_code": _paypal_currency(), "value": plan["price"]},
                    "custom_id": user_id,  # ✅ amarra la compra al usuario
                }
            ],
        }

        r = requests.post(
            f"{base_url}/v2/checkout/orders",
            headers=_paypal_headers(access_token),
            data=json.dumps(payload),
            timeout=20,
        )

        if r.status_code not in (200, 201):
            current_app.logger.error("PAYPAL_CREATE_ORDER_ERROR %s %s", r.status_code, r.text)
            return jsonify({"error": "paypal_create_order_failed"}), 502

        order = r.json() or {}
        order_id = str(order.get("id") or "").strip()

        if not order_id:
            current_app.logger.error("PAYPAL_CREATE_ORDER_NO_ID %s", order)
            return jsonify({"error": "paypal_create_order_no_id"}), 502

        current_app.logger.info("PAYPAL_CREATE_ORDER_OK user=%s plan=%s order_id=%s", user_id, plan_key, order_id)
        return jsonify({"ok": True, "orderID": order_id})

    except Exception as e:
        current_app.logger.exception("PAYPAL_CREATE_ORDER_EXCEPTION %s", e)
        return jsonify({"error": "paypal_create_order_exception"}), 500


# -----------------------------------------------------
# API: CAPTURE ORDER (server-side)
# POST /api/paypal/capture-order
# Body: { orderID: "..." }
# -----------------------------------------------------
@api_bp.post("/capture-order")
def paypal_capture_order():
    if not current_app.config.get("PAYPAL_ENABLED", False):
        return jsonify({"error": "PayPal no está habilitado en el servidor."}), 400

    data: Dict[str, Any] = request.get_json(silent=True) or {}
    order_id = (data.get("orderID") or data.get("order_id") or "").strip()

    if not order_id:
        return jsonify({"error": "orderID requerido"}), 400

    user_id = _get_user_id()

    # ✅ 1) Bloquear guest
    blocked = _require_login_or_401(user_id)
    if blocked:
        return blocked

    # ✅ Anti doble crédito
    existing = Payment.query.filter_by(order_id=order_id).first()
    if existing:
        current_app.logger.warning("PAYPAL_CAPTURE_DUPLICATE order_id=%s user=%s", order_id, user_id)
        return jsonify(
            {
                "ok": True,
                "already_recorded": True,
                "status": (existing.status or "").strip(),
                "user_id": existing.user_id,
                "credited_minutes": int(existing.minutes or 0),
                "order_id": order_id,
            }
        ), 200

    try:
        access_token = _paypal_get_access_token()
        base_url = _paypal_base_url()

        r = requests.post(
            f"{base_url}/v2/checkout/orders/{order_id}/capture",
            headers=_paypal_headers(access_token),
            timeout=25,
        )

        if r.status_code not in (200, 201):
            current_app.logger.error("PAYPAL_CAPTURE_ERROR %s %s", r.status_code, r.text)
            return jsonify({"error": "paypal_capture_failed"}), 502

        cap: Dict[str, Any] = r.json() or {}
        status = str(cap.get("status") or "").strip().upper()

        # ✅ 2) SOLO COMPLETED acredita y SOLO ahí status="captured"
        if status != "COMPLETED":
            current_app.logger.warning("PAYPAL_CAPTURE_NOT_COMPLETED status=%s payload=%s", status, cap)
            return jsonify({"error": "payment_not_completed", "status": status, "order_id": order_id}), 400

        # ✅ seguridad: custom_id debe coincidir con user_id
        custom_id = _extract_custom_id(cap)
        if custom_id and custom_id != user_id:
            current_app.logger.error(
                "PAYPAL_CUSTOM_ID_MISMATCH order_id=%s expected_user=%s custom_id=%s",
                order_id, user_id, custom_id
            )
            return jsonify({"error": "user_mismatch"}), 400

        capture_id, paid_value, paid_currency = _extract_capture_info(cap)

        if paid_currency != _paypal_currency():
            current_app.logger.warning("PAYPAL_CURRENCY_MISMATCH %s != %s", paid_currency, _paypal_currency())
            return jsonify({"error": "currency_mismatch"}), 400

        plan_key: Optional[str] = _find_plan_by_amount(paid_value)
        if not plan_key:
            current_app.logger.warning("PAYPAL_AMOUNT_NOT_ALLOWED %s %s", paid_currency, paid_value)
            return jsonify({"error": "amount_not_allowed"}), 400

        plan = PLANS[plan_key]
        minutes = int(plan["minutes"])
        sku = plan["sku"]

        payment = Payment(
            user_id=user_id,
            order_id=order_id,
            sku=sku,
            minutes=minutes,
            amount_usd=float(paid_value),
            status="captured",  # ✅ solo aquí porque ya es COMPLETED
            raw_payload=cap,
        )
        # Si tu modelo Payment tiene capture_id, lo seteamos si existe
        if hasattr(payment, "capture_id"):
            setattr(payment, "capture_id", capture_id)

        db.session.add(payment)
        db.session.commit()

        current_app.logger.info(
            "PAYPAL_CAPTURE_OK user=%s plan=%s minutes=%s order_id=%s capture_id=%s",
            user_id, plan_key, minutes, order_id, capture_id
        )

        # ✅ usage.py sumará esto automáticamente (paid_min)
        return jsonify(
            {
                "ok": True,
                "status": status,  # ✅ frontend usa esto para confirmar COMPLETED
                "user_id": user_id,
                "order_id": order_id,
                "capture_id": capture_id,
                "plan": plan_key,
                "credited_minutes": minutes,
                "amount": paid_value,
                "currency": paid_currency,
            }
        ), 200

    except Exception as e:
        current_app.logger.exception("PAYPAL_CAPTURE_EXCEPTION %s", e)
        return jsonify({"error": "paypal_capture_exception"}), 500
