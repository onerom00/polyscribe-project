# app/routes/ayuda.py
from flask import Blueprint, render_template, request

bp = Blueprint("ayuda", __name__)

@bp.route("/ayuda")
def ayuda():
    # si vienes con ?user_id=... lo pasamos al template para que el nav lo preserve
    return render_template("ayuda.html", user_id=request.args.get("user_id", ""))
