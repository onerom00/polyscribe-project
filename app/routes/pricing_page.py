# app/routes/pricing_page.py
import os
from flask import Blueprint, render_template, request

bp = Blueprint("pricing_page", __name__)

@bp.route("/pricing")
def pricing():
    client_id = os.getenv("PAYPAL_CLIENT_ID", "") or ""
    currency = os.getenv("PAYPAL_CURRENCY", "USD") or "USD"
    user_id = request.args.get("user_id", "") or ""
    return render_template(
        "pricing.html",
        paypal_client_id=client_id,
        paypal_currency=currency,
        user_id=user_id,
    )

