# app/routes/pages.py
from __future__ import annotations
import os

from flask import (
    Blueprint,
    render_template,
    current_app,
    send_from_directory,
    abort,
    request,
    redirect,
    url_for,
)

bp = Blueprint("pages", __name__)


def _try_render(template_name: str, **context):
    """
    Intenta renderizar un template si existe; si no, busca un archivo estático.

    Ahora acepta **context para poder pasar variables al template
    (por ejemplo, paypal_enabled en pricing.html).
    """
    tmpl_folder = (
        current_app.jinja_loader.searchpath
        if hasattr(current_app, "jinja_loader")
        else []
    )

    # 1) Buscar template en la carpeta de templates
    for p in tmpl_folder or []:
        if os.path.exists(os.path.join(p, template_name)):
            return render_template(template_name, **context)

    # 2) Si no hay template, probar como archivo estático
    static_folder = current_app.static_folder or "static"
    static_path = os.path.join(static_folder, template_name)
    if os.path.exists(static_path):
        return send_from_directory(static_folder, template_name)

    # 3) Nada encontrado
    abort(404, f"{template_name} no encontrado")


# ------------------------------
# PÁGINAS PRINCIPALES
# ------------------------------

@bp.get("/")
def index():
    # Página principal: transcriptor
    return _try_render("index.html")


@bp.get("/transcribir")
def transcribir():
    """
    Pestaña 'Transcribir' del menú.
    La hacemos apuntar SIEMPRE a la página principal del transcriptor.
    """
    return redirect(url_for("pages.index"))


@bp.get("/history")
def history():
    return _try_render("history.html")


@bp.get("/pricing")
def pricing():
    # Le pasamos al template si PayPal está habilitado según la config
    paypal_enabled = current_app.config.get("PAYPAL_ENABLED", False)
    return _try_render("pricing.html", paypal_enabled=paypal_enabled)


@bp.get("/ayuda")
def ayuda():
    return _try_render("ayuda.html")


# ------------------------------
# DEV LOGIN (solo para pruebas)
# ------------------------------

@bp.get("/dev-login")
def dev_login():
    """
    Pantalla de login/registro de prueba para guardar ps_user_id en localStorage.
    """
    is_signup = request.args.get("signup") == "1"
    return render_template("dev_login.html", is_signup=is_signup)


# ------------------------------
# FAVICON
# ------------------------------

@bp.get("/favicon.ico")
def favicon():
    static_folder = current_app.static_folder or "static"
    path = os.path.join(static_folder, "favicon.ico")
    if os.path.exists(path):
        return send_from_directory(static_folder, "favicon.ico")
    abort(404)
