# app/routes/usage.py
from __future__ import annotations

import os

from flask import Blueprint, current_app, jsonify, session

from app import db
from app.models import AudioJob
from app.models_payment import Payment

bp = Blueprint("usage", __name__, url_prefix="/api/usage")

MB = 1024 * 1024
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100") or 100)


def _session_user_id() -> str:
    """
    ✅ Fuente de verdad: sesión.
    NO aceptamos X-User-Id, ni ?user_id, ni DEV_USER_ID (rompe unicidad).
    """
    raw = session.get("user_id") or session.get("uid")
    uid = str(raw).strip() if raw else ""
    return uid


def _user_id_variants(user_id: str) -> list[str]:
    """
    Compatibilidad con datos históricos:
    - algunos registros viejos pudieron guardar "id-<uid>" o "<uid>"
    """
    u = (user_id or "").strip()
    if not u:
        return []

    variants = {u}
    if u.startswith("id-") and len(u) > 3:
        variants.add(u[3:])
    else:
        variants.add("id-" + u)

    return list(variants)


def _guest_balance_payload():
    """
    ✅ Guest limpio:
    - usado 0
    - allowance 0 (para que el UI muestre “—” o 0 sin inventar)
    - sin muñequito (eso lo controla el front al ver authenticated=false)
    """
    return {
        "ok": True,
        "authenticated": False,
        "used_seconds": 0,
        "allowance_seconds": 0,
        "file_limit_bytes": int(MAX_UPLOAD_MB * MB),
    }


@bp.get("/whoami")
def whoami():
    """
    Devuelve el estado real de sesión.
    """
    uid = _session_user_id()
    if not uid:
        return jsonify({"ok": True, "authenticated": False, "user_id": None}), 200
    return jsonify({"ok": True, "authenticated": True, "user_id": uid}), 200


@bp.get("/balance")
def usage_balance():
    """
    ✅ Balance estable:
    - Si NO hay sesión => devolvemos guest limpio (NO 401)
    - Si hay sesión => devolvemos balance real
    """
    user_id = _session_user_id()
    if not user_id:
        return jsonify(_guest_balance_payload()), 200

    free_min = int(current_app.config.get("FREE_TIER_MINUTES", 5))

    # Variantes derivadas del user_id de sesión (compatibilidad)
    uid_variants = _user_id_variants(user_id)

    # ---- Paid minutes ----
    paid_min = 0
    try:
        q = db.session.query(Payment).filter(
            Payment.user_id.in_(uid_variants),
            Payment.status == "captured",
        )
        paid_min = sum(int(p.minutes or 0) for p in q.all())
    except Exception as e:
        current_app.logger.error("usage_balance: error leyendo pagos: %s", e)
        paid_min = 0

    # ---- Used seconds (jobs) ----
    used_seconds = 0
    try:
        qj = db.session.query(AudioJob).filter(AudioJob.user_id.in_(uid_variants))
        used_seconds = sum(int(j.duration_seconds or 0) for j in qj.all())
    except Exception as e:
        current_app.logger.error("usage_balance: error leyendo jobs: %s", e)
        used_seconds = 0

    allowance_min = free_min + paid_min
    allowance_seconds = int(allowance_min * 60)

    current_app.logger.info(
        "USAGE_BALANCE session_uid=%s variants=%s used_seconds=%s allowance_seconds=%s free_min=%s paid_min=%s",
        user_id,
        uid_variants,
        used_seconds,
        allowance_seconds,
        free_min,
        paid_min,
    )

    return jsonify(
        {
            "ok": True,
            "authenticated": True,
            "user_id": user_id,
            "used_seconds": int(used_seconds),
            "allowance_seconds": int(allowance_seconds),
            "file_limit_bytes": int(MAX_UPLOAD_MB * MB),
        }
    ), 200
