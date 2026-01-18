# app/routes/usage.py
from __future__ import annotations

import os

from flask import Blueprint, current_app, jsonify, request, session

from app import db
from app.models import AudioJob
from app.models_payment import Payment

bp = Blueprint("usage", __name__, url_prefix="/api/usage")

MB = 1024 * 1024
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100") or 100)


def _get_user_id() -> str:
    raw = (
        session.get("user_id")
        or session.get("uid")
        or request.headers.get("X-User-Id")
        or request.args.get("user_id")
        or os.getenv("DEV_USER_ID", "")
    )
    s = str(raw).strip() if raw else ""
    return s or "guest"


def _user_id_variants(user_id: str) -> list[str]:
    """
    Compat: en tu app se ven dos formatos:
      - "id-xxxxx"
      - "xxxxx"
    Para pagos, aceptamos ambos para no perder créditos.
    """
    u = (user_id or "").strip()
    if not u:
        return ["guest"]

    variants = {u}

    if u.startswith("id-") and len(u) > 3:
        variants.add(u[3:])  # sin prefijo
    else:
        variants.add("id-" + u)  # con prefijo

    return list(variants)


@bp.get("/balance")
def usage_balance():
    user_id = _get_user_id()
    free_min = int(current_app.config.get("FREE_TIER_MINUTES", 10))

    # ✅ Variantes aceptadas SOLO para pagos
    pay_uids = _user_id_variants(user_id)

    # Minutos pagados (captured)
    paid_min = 0
    try:
        q = db.session.query(Payment).filter(
            Payment.user_id.in_(pay_uids),
            Payment.status == "captured",
        )
        paid_min = sum(int(p.minutes or 0) for p in q.all())
    except Exception as e:
        current_app.logger.error("usage_balance: error leyendo pagos: %s", e)
        paid_min = 0

    # Segundos usados (jobs) -> aquí mantenemos SOLO el user_id actual
    used_seconds = 0
    try:
        qj = db.session.query(AudioJob).filter(AudioJob.user_id == user_id)
        used_seconds = sum(int(j.duration_seconds or 0) for j in qj.all())
    except Exception as e:
        current_app.logger.error("usage_balance: error leyendo jobs: %s", e)
        used_seconds = 0

    allowance_min = free_min + paid_min
    allowance_seconds = int(allowance_min * 60)

    current_app.logger.info(
        "USAGE_BALANCE uid=%s pay_uids=%s used_seconds=%s allowance_seconds=%s free_min=%s paid_min=%s",
        user_id,
        pay_uids,
        used_seconds,
        allowance_seconds,
        free_min,
        paid_min,
    )

    return jsonify(
        {
            "ok": True,
            "used_seconds": int(used_seconds),
            "allowance_seconds": int(allowance_seconds),
            "file_limit_bytes": int(MAX_UPLOAD_MB * MB),
        }
    )
