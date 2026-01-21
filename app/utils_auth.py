# app/utils_auth.py
from __future__ import annotations
from flask import request, session

def get_request_user_id() -> int | None:
    """
    Obtiene el user_id de (prioridad):
    - header X-User-Id (modo DEV / curl)
    - querystring ?user_id=
    - session['user_id'] / session['uid']
    Devuelve int o None si no hay.
    """
    # header
    h = request.headers.get("X-User-Id") or request.headers.get("x-user-id")
    if h:
        try:
            return int(h)
        except Exception:
            pass

    # querystring
    qs = request.args.get("user_id")
    if qs:
        try:
            return int(qs)
        except Exception:
            pass

    # session
    for k in ("user_id", "uid"):
        if k in session:
            try:
                return int(session[k])
            except Exception:
                pass

    return None
