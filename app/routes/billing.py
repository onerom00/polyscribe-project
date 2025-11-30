# app/routes/billing.py
from __future__ import annotations

from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import select

from .. import db
from ..models_payment import Payment
from ..models import User  # asumiendo User en app/models.py

bp = Blueprint("billing", __name__, url_prefix="/api/billing")


def _resolve_user():
    raw = request.headers.get("X-User-Id") or request.args.get("user_id")
    if not raw:
        dev = current_app.config.get("DEV_USER_ID")
        raw = str(dev) if dev else None
    try:
        uid = int(raw) if raw else None
    except Exception:
        uid = None

    if not uid:
        return None

    return db.session.execute(select(User).where(User.id == uid)).scalars().first()


@bp.get("/invoices")
def list_invoices():
    """
    Devuelve lista JSON de compras del usuario autenticado (simple).
    """
    user = _resolve_user()
    if not user:
        return jsonify({"error": "Usuario no resuelto."}), 401

    rows = db.session.execute(
        select(Payment).where(Payment.user_id == user.id).order_by(Payment.id.desc())
    ).scalars().all()

    items = []
    for r in rows:
        items.append({
            "id": r.id,
            "order_id": r.order_id,
            "status": r.status,
            "currency": r.currency,
            "amount_value": r.amount_value,
            "minutes": r.minutes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return jsonify({"items": items})


@bp.get("/invoices/<int:pid>")
def get_invoice(pid: int):
    """
    Detalle simple de una compra (para un futuro PDF/recibo).
    """
    user = _resolve_user()
    if not user:
        return jsonify({"error": "Usuario no resuelto."}), 401

    p = db.session.get(Payment, pid)
    if not p or p.user_id != user.id:
        return jsonify({"error": "No encontrado."}), 404

    return jsonify({
        "id": p.id,
        "order_id": p.order_id,
        "status": p.status,
        "currency": p.currency,
        "amount_value": p.amount_value,
        "minutes": p.minutes,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "raw_json": p.raw_json,
    })
