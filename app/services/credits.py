from __future__ import annotations

import os

from flask import current_app

from app.extensions import db
from app.models import AudioJob
from app.models_payment import Payment


def get_free_tier_minutes() -> int:
    """
    Fuente robusta para el plan gratis:
    1) Variable de entorno FREE_TIER_MINUTES
    2) Config Flask FREE_TIER_MINUTES
    3) Default seguro: 5 minutos
    """
    raw = os.getenv("FREE_TIER_MINUTES", current_app.config.get("FREE_TIER_MINUTES", 5))
    try:
        return int(raw or 5)
    except Exception:
        return 5


def get_allowance_seconds(user_id: str) -> int:
    free_min = get_free_tier_minutes()

    paid_min = 0
    q = db.session.query(Payment).filter(
        Payment.user_id == user_id,
        Payment.status == "captured",
    )
    paid_min = sum(int(p.minutes or 0) for p in q.all())

    allowance_seconds = int((free_min + paid_min) * 60)
    return allowance_seconds


def get_used_seconds(user_id: str) -> int:
    qj = db.session.query(AudioJob).filter(AudioJob.user_id == user_id)
    used_seconds = sum(int(j.duration_seconds or 0) for j in qj.all())
    return int(used_seconds)


def get_remaining_seconds(user_id: str) -> int:
    allow = get_allowance_seconds(user_id)
    used = get_used_seconds(user_id)
    return max(0, allow - used)