# app/routes/account_page.py
from __future__ import annotations

from flask import Blueprint, render_template, g

bp = Blueprint("account_page", __name__)

@bp.get("/account")
def account_page():
    # Si quieres forzar login aquí, lo hacemos luego.
    # Por ahora: muestra la página y el JS decide si está logueado.
    return render_template("account.html", user_id=getattr(g, "user_id", "") or "")
