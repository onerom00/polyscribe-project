# app/billing.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone

UTC = timezone.utc


def now_utc_naive() -> datetime:
    """
    Devuelve UTC naive (sin tzinfo) para compatibilidad con SQLite/Postgres
    """
    return datetime.now(tz=UTC).replace(tzinfo=None)


def compute_cycle_window(days: int = 31) -> tuple[datetime, datetime]:
    """
    Utilidad para calcular ciclo (start, end).
    No toca DB ni modelos, así evitamos duplicidad.
    """
    start = now_utc_naive()
    end = start + timedelta(days=int(days or 31))
    return start, end
