# app/billing.py
from datetime import datetime, timedelta, timezone
from typing import Optional
from .models import User, UsageLedger, UsageReason

UTC = timezone.utc

def now_utc() -> datetime:
    return datetime.now(tz=UTC).replace(tzinfo=None)  # SQLite sin TZ

def grant_cycle(user: User, plan_tier: str, quota_minutes: int, days: int = 31, note: str = "") -> None:
    """
    Asigna/renueva ciclo: setea tier, cuota total y resetea el consumo.
    Registra un evento 'grant_cycle' (solo auditoría; no descuenta minutos).
    """
    start = now_utc()
    end = start + timedelta(days=days)

    user.plan_tier = plan_tier
    user.cycle_start = start
    user.cycle_end = end
    user.minute_quota = int(quota_minutes or 0)
    user.minutes_used = 0
    user.is_active = True

    ev = UsageLedger(
        user_id=user.id,
        job_id=None,
        minutes_delta=0,
        reason=UsageReason.grant_cycle,
        note=note or f"{plan_tier} {quota_minutes}m {days}d"
    )
    return ev  # recuerda hacer db.add(ev)

def charge_minutes(user: User, minutes: int) -> None:
    user.minutes_used = max(0, int(user.minutes_used or 0) + int(minutes or 0))
