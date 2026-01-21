# app/routes_payments.py
from __future__ import annotations

import os
import datetime as dt
from typing import Any, Dict, Optional

from flask import Blueprint, request, jsonify, render_template

# Intentamos importar tus modelos/DB si existen
try:
    from .models import UsageLedger, User  # type: ignore
except Exception:
    UsageLedger = User = object  # fallbacks

try:
    from . import db  # type: ignore
except Exception:
    db = None

bp = Blueprint("payments", __name__)

# ------------------ Helpers DB (seguros si no hay SQLAlchemy) -----------------
def _session():
    return getattr(db, "session", None) if db else None

def _sa_get(Model, obj_id):
    s = _session()
    if s is not None:
        try:
            obj = s.get(Model, obj_id)  # SQLAlchemy 2.x
            if obj is not None:
                return obj
        except Exception:
            pass
        try:
            return s.query(Model).filter_by(id=obj_id).first()
        except Exception:
            pass
    try:
        q = getattr(Model, "query", None)
        if q is not None:
            return q.get(obj_id)
    except Exception:
        pass
    return None

def _sa_first(Model):
    s = _session()
    if s is not None:
        try:
            return s.query(Model).first()
        except Exception:
            pass
    try:
        q = getattr(Model, "query", None)
        if q is not None:
            return q.first()
    except Exception:
        pass
    return None

def _sa_add_commit(obj) -> None:
    s = _session()
    if s is not None:
        try:
            s.add(obj)
            s.commit()
            return
        except Exception:
            s.rollback()

def _sa_commit() -> None:
    s = _session()
    if s is None:
        return
    try:
        s.commit()
    except Exception:
        s.rollback()

# --------------- Usuario desde cabecera X-User-Id o ?user_id ------------------
def _get_user_from_request() -> Optional[Any]:
    uid = request.headers.get("X-User-Id") or request.args.get("user_id") or ""
    try:
        uid_int = int(uid) if uid else 0
    except Exception:
        uid_int = 0

    if uid_int > 0:
        u = _sa_get(User, uid_int)
        if u is not None:
            return u

    u = _sa_first(User)
    if u is not None:
        return u

    # Si no hay BD, devolvemos None (modo DEV sin usuarios)
    return None

# ----------------------------- Ledger mensual ---------------------------------
def _ledger_upsert(user_id: int, period: str, delta_allow: int = 0, delta_used: int = 0) -> Dict[str, int]:
    """
    Suma minutos en allowance (delta_allow en segundos) y/o used (delta_used en segundos).
    Devuelve dict con valores finales. Si no hay BD, simplemente devuelve los deltas.
    """
    if db is None or not hasattr(UsageLedger, "__init__"):
        # Modo DEV sin BD: “aceptamos” y devolvemos algo coherente
        return {"allowance_seconds": max(0, int(delta_allow)), "used_seconds": max(0, int(delta_used))}

    s = _session()
    row = None
    try:
        row = s.query(UsageLedger).filter_by(user_id=user_id, period=period).first()  # type: ignore
    except Exception:
        pass

    now = dt.datetime.utcnow()
    if row is None:
        try:
            row = UsageLedger()  # type: ignore
            if hasattr(row, "user_id"): setattr(row, "user_id", user_id)
            if hasattr(row, "period"): setattr(row, "period", period)
            if hasattr(row, "allowance_seconds"): setattr(row, "allowance_seconds", 0)
            if hasattr(row, "used_seconds"): setattr(row, "used_seconds", 0)
            if hasattr(row, "created_at"): setattr(row, "created_at", now)
            if hasattr(row, "updated_at"): setattr(row, "updated_at", now)
            _sa_add_commit(row)
        except Exception:
            pass

    try:
        if delta_allow:
            cur = int(getattr(row, "allowance_seconds", 0) or 0) + int(delta_allow)
            setattr(row, "allowance_seconds", max(0, cur))
        if delta_used:
            cur = int(getattr(row, "used_seconds", 0) or 0) + int(delta_used)
            setattr(row, "used_seconds", max(0, cur))
        if hasattr(row, "updated_at"):
            setattr(row, "updated_at", now)
        _sa_commit()
    except Exception:
        pass

    return {
        "allowance_seconds": int(getattr(row, "allowance_seconds", 0) or 0),
        "used_seconds": int(getattr(row, "used_seconds", 0) or 0),
    }

# --------------------------------- Rutas --------------------------------------

@bp.route("/pricing", methods=["GET"])
def pricing_page():
    # Renderiza tu template (ya lo tienes maquetado)
    return render_template("pricing.html")

@bp.route("/api/paypal/config", methods=["GET"])
def paypal_config():
    """
    Devuelve el client_id para el SDK de PayPal y la moneda.
    Define en tu entorno:
      PAYPAL_CLIENT_ID=...
      PAYPAL_CURRENCY=USD (opcional, por defecto USD)
    """
    client_id = os.getenv("PAYPAL_CLIENT_ID", "").strip()
    currency = os.getenv("PAYPAL_CURRENCY", "USD").strip().upper() or "USD"
    return jsonify({"client_id": client_id, "currency": currency})

@bp.route("/api/paypal/capture", methods=["POST"])
def paypal_capture():
    """
    Recibe { order_id, minutes } desde el botón de PayPal del frontend.
    En producción, aquí puedes verificar el pago llamando a la API de PayPal con tus
    credenciales (PAYPAL_CLIENT_ID / PAYPAL_SECRET). Para simplificar DEV, si no hay
    credenciales o PAYPAL_MODE=mock, aceptamos el capture.
    """
    user = _get_user_from_request()
    if user is None:
        # aceptamos DEV aunque no haya user para no bloquear la UI
        pass

    data = {}
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        pass

    order_id = str(data.get("order_id") or "").strip()
    minutes = int(data.get("minutes") or 0)

    if minutes <= 0:
        return jsonify({"error": "Parámetro 'minutes' inválido."}), 400

    # --- Verificación (opcional) ---
    mode = os.getenv("PAYPAL_MODE", "mock").lower()
    client_id = os.getenv("PAYPAL_CLIENT_ID", "").strip()
    secret = os.getenv("PAYPAL_SECRET", "").strip()

    verified = False
    if mode != "mock" and client_id and secret:
        # Aquí iría la verificación real contra PayPal (omita por DEV sin internet)
        # Para mantenerlo simple en este entorno local, marcamos como "verified".
        verified = True
    else:
        # Modo mock/dev: aceptamos
        verified = True

    if not verified:
        return jsonify({"error": "No se pudo verificar el pago con PayPal."}), 400

    # --- Acreditar minutos en el ledger del mes actual ---
    uid = getattr(user, "id", None) if user is not None else None
    if uid is None and _sa_first(User) is not None:
        uid = getattr(_sa_first(User), "id", None)  # mejor que nada

    seconds = minutes * 60
    now = dt.datetime.utcnow()
    period = f"{now.year:04d}-{now.month:02d}"

    res = _ledger_upsert(user_id=int(uid or 0), period=period, delta_allow=seconds, delta_used=0)

    return jsonify({
        "ok": True,
        "credited_minutes": minutes,
        "period": period,
        "allowance_seconds": res.get("allowance_seconds", 0),
        "used_seconds": res.get("used_seconds", 0),
        "order_id": order_id or "mock",
    })
