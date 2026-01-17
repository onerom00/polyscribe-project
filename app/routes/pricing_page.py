# app/routes/pricing_page.py
from flask import Blueprint, render_template, request, current_app

bp = Blueprint("pricing_page", __name__)

@bp.route("/pricing")
def pricing():
    user_id = request.args.get("user_id", "") or ""
    return render_template(
        "pricing.html",
        user_id=user_id,
        paypal_enabled=current_app.config.get("PAYPAL_ENABLED", False),
    )

