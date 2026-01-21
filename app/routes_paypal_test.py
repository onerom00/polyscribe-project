# app/routes_paypal_test.py
from __future__ import annotations
import os, datetime as dt
from flask import Blueprint, request, jsonify, session, current_app
from app import db

try:
    from app.models_payment import Payment
except Exception:
    Payment = None  # type: ignore

bp = Blueprint("paypal_test", __name__)

def _uid():
    raw = session.get("uid") or request.headers.get("X-User-Id") or request.args.get("user_id")
    try:
        return int(raw) if raw else None
    except Exception:
        return None

@bp.route("/api/paypal/simulate_capture", methods=["POST"])
def simulate_capture():
    """
    SOLO pruebas locales.
    Habilita con: PAYPAL_TEST_MODE=1 (o 'true')
    Body JSON: {"sku":"starter_60","minutes":60,"amount":"9.00"}
    """
    if os.getenv("PAYPAL_TEST_MODE", "0") not in ("1", "true", "True"):
        return jsonify({"ok": False, "error": "disabled"}), 404

    uid = _uid()
    if not uid:
        return jsonify({"ok": False, "error": "auth required"}), 401

    data = request.get_json(silent=True) or {}
    sku = (data.get("sku") or "").strip()
    minutes = int(data.get("minutes") or 0)
    amount = str(data.get("amount") or "0.00")
    if not sku or minutes <= 0:
        return jsonify({"ok": False, "error": "sku/minutes required"}), 400

    pid = None
    if Payment is not None:
        try:
            p = Payment(
                user_id=uid,
                provider="paypal",
                status="captured",
                minutes=minutes,
                amount=amount,
                currency=(os.getenv("PAYPAL_CURRENCY", "USD") or "USD"),
                ref="SIM-" + sku,
                created_at=getattr(Payment, "created_at", None) and dt.datetime.utcnow() or None,
                updated_at=getattr(Payment, "updated_at", None) and dt.datetime.utcnow() or None,
            )
            db.session.add(p); db.session.commit()
            pid = getattr(p, "id", None)
        except Exception as e:
            current_app.logger.exception("simulate_capture save failed: %s", e)
            db.session.rollback()

    return jsonify({"ok": True, "minutes": minutes, "sku": sku, "payment_id": pid})
