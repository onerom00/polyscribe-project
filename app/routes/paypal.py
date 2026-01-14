from flask import Blueprint, request, jsonify, current_app
from app.extensions import db
from app.models_user import User

bp = Blueprint("paypal", __name__, url_prefix="/api/paypal")


PLAN_MINUTES = {
    "starter": 60,
    "pro": 300,
    "business": 1200,
}


@bp.route("/webhook", methods=["POST"])
def paypal_webhook():
    payload = request.get_json(silent=True)

    if not payload:
        return jsonify({"error": "empty payload"}), 400

    event_type = payload.get("event_type")

    current_app.logger.info(f"PAYPAL WEBHOOK: {event_type}")

    if event_type != "PAYMENT.CAPTURE.COMPLETED":
        return jsonify({"status": "ignored"}), 200

    resource = payload.get("resource", {})
    payer_email = (
        resource.get("payer", {})
        .get("email_address")
    )

    purchase_units = payload.get("resource", {}).get("purchase_units", [])
    custom_id = purchase_units[0].get("custom_id") if purchase_units else None

    if not payer_email or not custom_id:
        current_app.logger.error("Webhook incompleto")
        return jsonify({"error": "invalid payload"}), 400

    minutes = PLAN_MINUTES.get(custom_id)

    if not minutes:
        current_app.logger.error(f"Plan desconocido: {custom_id}")
        return jsonify({"error": "invalid plan"}), 400

    user = db.session.query(User).filter_by(email=payer_email).first()

    if not user:
        return jsonify({"error": "user not found"}), 404

    # 🔥 ACREDITAR MINUTOS (ACUMULABLE)
    user.minute_quota += minutes * 60
    db.session.commit()

    current_app.logger.info(
        f"MINUTOS ACREDITADOS: {minutes} a {user.email}"
    )

    return jsonify({"status": "ok"}), 200
