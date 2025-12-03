# app/routes/paypal.py
from __future__ import annotations

import datetime as dt
from typing import Optional

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    request,
)

from app import db
from app.paypal_sdk import PayPalSDK
from app.models_payment import Payment, PaymentEvent

# Importamos los modelos de uso de minutos
from app.models import UsageLedger, UsageLedgerEvent  # type: ignore[attr-defined]


bp = Blueprint("paypal", __name__, url_prefix="/paypal")


# -------------------------------------------------
# Utilidades internas
# -------------------------------------------------
def _utcnow() -> dt.datetime:
    return dt.datetime.utcnow()


def _plan_code_from_plan_id(plan_id: Optional[str]) -> Optional[str]:
    """
    Traduce el plan_id de PayPal a tu código interno ("starter", etc).
    Por ahora tenemos sólo el Starter.
    """
    if not plan_id:
        return None

    starter_id = current_app.config.get("PAYPAL_PLAN_STARTER_ID")
    if starter_id and plan_id == starter_id:
        return "starter"

    # 👀 aquí en el futuro puedes mapear PRO / BUSINESS:
    # pro_id = current_app.config.get("PAYPAL_PLAN_PRO_ID")
    # if plan_id == pro_id: return "pro"
    #
    # etc...
    return None


def _minutes_for_plan(plan_code: str) -> int:
    """
    Minutos que otorga cada plan.
    """
    mapping = {
        "starter": 60,
        # "pro": 300,
        # "business": 1200,
    }
    return mapping.get(plan_code, 0)


def _grant_plan_minutes(*, user_id: str, plan_code: str, payment: Payment) -> None:
    """
    Suma minutos al saldo del usuario en usage_ledger y registra un evento.
    """
    minutes = _minutes_for_plan(plan_code)
    if minutes <= 0:
        current_app.logger.warning(
            "Plan %s no tiene minutos configurados, no se acredita nada", plan_code
        )
        return

    ledger = UsageLedger.query.filter_by(user_id=user_id).first()
    if not ledger:
        ledger = UsageLedger(
            user_id=user_id,
            minutes_total=minutes,
            minutes_used=0,
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )
        db.session.add(ledger)
    else:
        ledger.minutes_total += minutes
        ledger.updated_at = _utcnow()

    db.session.add(
        UsageLedgerEvent(
            user_id=user_id,
            minutes_delta=minutes,
            reason=f"paypal_{plan_code}",
            payment_id=payment.id,
            created_at=_utcnow(),
        )
    )

    current_app.logger.info(
        "Acreditados %s minutos del plan %s a %s (payment_id=%s)",
        minutes,
        plan_code,
        user_id,
        payment.id,
    )


# -------------------------------------------------
# Gracias / Cancel
# -------------------------------------------------
@bp.get("/thanks")
def paypal_thanks():
    """
    Return URL que configuraste en PayPal.
    Aquí sólo mostramos la página de éxito y redirigimos al usuario a la app,
    el verdadero crédito de minutos lo hace el webhook.
    """
    user_id = request.args.get("user_id", "guest")
    # plan es algo como ?plan=starter
    plan_code = request.args.get("plan", "starter")

    current_app.logger.info(
        "PayPal /thanks recibido para user_id=%s plan=%s", user_id, plan_code
    )

    # Redirigimos a la home con el user_id en la query para que nav_auth.js
    # muestre el saldo correcto.
    return redirect(f"/?user_id={user_id}")


@bp.get("/cancel")
def paypal_cancel():
    """
    Si el usuario cancela en PayPal.
    """
    return redirect("/pricing?cancel=1")


# -------------------------------------------------
# Webhook
# -------------------------------------------------
@bp.post("/webhook")
def paypal_webhook():
    """
    Endpoint que recibe las notificaciones de PayPal.
    Aquí:
      1) Guardamos el evento completo en payment_events.
      2) Si es BILLING.SUBSCRIPTION.ACTIVATED, creamos/actualizamos Payment.
      3) Acreditamos minutos al usuario correspondiente (según el plan).
    """
    event = request.get_json(silent=True) or {}
    event_type = event.get("event_type", "UNKNOWN")
    resource = event.get("resource") or {}
    subscription_id = resource.get("id")
    plan_id = resource.get("plan_id")
    custom_id = resource.get("custom_id")
    subscriber_email = (resource.get("subscriber") or {}).get("email_address")

    current_app.logger.info(
        "PayPal webhook recibido: type=%s subscription_id=%s",
        event_type,
        subscription_id,
    )

    # Intentamos encontrar el Payment asociado (si ya existía)
    payment = None
    if subscription_id:
        payment = Payment.query.filter_by(
            paypal_subscription_id=subscription_id
        ).first()

    pe = PaymentEvent(
        payment_id=payment.id if payment else None,
        event_type=event_type,
        resource_id=subscription_id,
        raw_json=event,
    )
    db.session.add(pe)

    # Sólo nos interesa acreditar minutos cuando la suscripción pasa a ACTIVA
    if event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
        user_id = custom_id or subscriber_email
        plan_code = _plan_code_from_plan_id(plan_id)

        if not user_id or not plan_code:
            current_app.logger.warning(
                "Webhook ACTIVED sin user_id o sin plan_code: user_id=%s, plan_id=%s",
                user_id,
                plan_id,
            )
        else:
            if not payment:
                payment = Payment(
                    user_id=user_id,
                    plan_code=plan_code,
                    paypal_subscription_id=subscription_id or "",
                    status="active",
                    currency=current_app.config.get("PAYPAL_CURRENCY", "USD"),
                    raw_payload=resource,
                )
                db.session.add(payment)
                db.session.flush()  # para tener payment.id
            else:
                payment.status = "active"
                payment.raw_payload = resource

            _grant_plan_minutes(user_id=user_id, plan_code=plan_code, payment=payment)

    db.session.commit()
    return jsonify({"status": "ok"})
