# app/routes_ui.py
from flask import Blueprint, render_template, request, current_app

bp = Blueprint("ui", __name__, url_prefix="")

@bp.get("/")
def home():
    # Usamos el user_id por query o el de desarrollo
    uid = request.args.get("user_id", type=int) or current_app.config.get("DEV_USER_ID")
    return render_template("index.html", user_id=uid)
