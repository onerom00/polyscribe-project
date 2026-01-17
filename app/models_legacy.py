from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional  # noqa: F401

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
    Enum as SAEnum,
    JSON,
    Index,
    UniqueConstraint,
    CheckConstraint,
    func,
)
from sqlalchemy.orm import relationship

from .database import Base


# ---------- Mixins ----------
class TimestampMixin:
    # Importante: default (lado ORM) + server_default (lado BD)
    created_at = Column(
        DateTime,
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
        server_default=func.now(),
    )


# ---------- Enums ----------
class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    done = "done"
    error = "error"


class UsageReason(str, Enum):
    job_charge = "job_charge"
    admin_adjust = "admin_adjust"
    grant_cycle = "grant_cycle"
    refund = "refund"


# ---------- Models ----------
class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=True)
    display_name = Column(String, nullable=True)

    # Suscripción / Billing
    plan_tier = Column(String, nullable=False, default="free")
    paypal_subscription_id = Column(String, nullable=True, index=True)
    cycle_start = Column(DateTime, nullable=True)
    cycle_end = Column(DateTime, nullable=True)

    # Cuotas (minutos por ciclo)
    minute_quota = Column(Integer, nullable=False, default=0)
    minutes_used = Column(Integer, nullable=False, default=0)

    # Estado
    is_active = Column(Boolean, nullable=False, default=True)

    # Relaciones
    jobs = relationship(
        "AudioJob",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    usage_events = relationship(
        "UsageLedger",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="desc(UsageLedger.created_at)",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} plan={self.plan_tier} used={self.minutes_used}/{self.minute_quota}>"

    @property
    def minutes_remaining(self) -> int:
        rem = int(self.minute_quota or 0) - int(self.minutes_used or 0)
        return rem if rem > 0 else 0

    def add_minutes(self, delta: int) -> None:
        self.minutes_used = max(0, int(self.minutes_used or 0) + int(delta or 0))


class AudioJob(Base, TimestampMixin):
    """Job de transcripción/síntesis."""
    __tablename__ = "audio_jobs"

    id = Column(Integer, primary_key=True)

    # Propietario
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    user = relationship("User", back_populates="jobs")

    # ---- Campos legacy presentes en tu tabla (compatibilidad) ----
    filename = Column(String(255), nullable=False, default="")
    language = Column(String(16), nullable=True)
    summaries = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)

    # Origen / archivo (actual)
    original_filename = Column(String, nullable=True)
    audio_s3_key = Column(String, nullable=False, default="")  # NOT NULL en tu DB
    local_path = Column(String, nullable=True)
    mime_type = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=True)

    # Estado del procesamiento
    status = Column(SAEnum(JobStatus), nullable=False, default=JobStatus.queued)
    error_message = Column(Text, nullable=True)

    # Idioma (nuevo)
    language_forced = Column(String(8), nullable=True)
    language_detected = Column(String(8), nullable=True)

    # Duración y modelo
    duration_seconds = Column(Integer, nullable=True, index=True)
    model_used = Column(String, nullable=True)

    # Resultados nuevos
    transcript = Column(Text, nullable=True)
    summary_json = Column(JSON, nullable=True)

    # Costeo opcional
    cost_cents = Column(Integer, nullable=True)

    __table_args__ = (
        CheckConstraint("length(language_forced) <= 8", name="ck_jobs_lang_forced_len"),
        CheckConstraint("length(language_detected) <= 8", name="ck_jobs_lang_detected_len"),
    )

    def __repr__(self) -> str:
        return f"<AudioJob id={self.id} user={self.user_id} status={self.status} dur={self.duration_seconds}s>"


class UsageLedger(Base, TimestampMixin):
    """Libro mayor de consumo/asignación de minutos (eventos por job/ajuste)."""
    __tablename__ = "usage_ledger_events"  # creada por migración 20250820_usage_events

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    user = relationship("User", back_populates="usage_events")

    job_id = Column(Integer, ForeignKey("audio_jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    minutes_delta = Column(Integer, nullable=False, default=0)   # + consumo ; - abono
    reason = Column(SAEnum(UsageReason), nullable=False, default=UsageReason.job_charge)
    note = Column(String, nullable=True)

    __table_args__ = (
        Index("ix_usage_events_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<UsageLedger user={self.user_id} delta={self.minutes_delta} reason={self.reason}>"


class PaymentEvent(Base, TimestampMixin):
    """Eventos de PayPal procesados (idempotencia + auditoría)."""
    __tablename__ = "payment_events"

    id = Column(Integer, primary_key=True)
    provider = Column(String, nullable=False, default="paypal")
    event_type = Column(String, nullable=False)
    external_event_id = Column(String, nullable=False)
    subscription_id = Column(String, nullable=True, index=True)
    payload = Column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("provider", "external_event_id", name="uq_payment_events_provider_event"),
        Index("ix_payment_sub_id_created", "subscription_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<PaymentEvent {self.provider}:{self.event_type} id={self.external_event_id}>"


# ---------- Helpers de compatibilidad ----------
def _calc_remaining_seconds(u: "User") -> int:
    allow = int(u.minute_quota or 0) * 60
    used = int(u.minutes_used or 0) * 60
    remain = allow - used
    return remain if remain > 0 else 0


def remaining_seconds_for_user(*args):
    """
    Compatibilidad con código previo:
      - remaining_seconds_for_user(user: User)
      - remaining_seconds_for_user(user_id: int, db: Session)
      - remaining_seconds_for_user(db: Session, user_id: int)
      - remaining_seconds_for_user(user_id: int)   # abre SessionLocal internamente
    """
    if not args:
        return 0

    first = args[0]
    if isinstance(first, User):
        return _calc_remaining_seconds(first)

    if len(args) >= 2:
        a, b = args[0], args[1]
        if hasattr(a, "query") and isinstance(b, int):
            u = a.query(User).get(b)
            return _calc_remaining_seconds(u) if u else 0
        if isinstance(a, int) and hasattr(b, "query"):
            u = b.query(User).get(a)
            return _calc_remaining_seconds(u) if u else 0

    if isinstance(first, int):
        try:
            from .database import SessionLocal
            db = SessionLocal()
            try:
                u = db.query(User).get(first)
                return _calc_remaining_seconds(u) if u else 0
            finally:
                db.close()
        except Exception:
            return 0

    return 0


def remaining_minutes_for_user(*args) -> int:
    """Conveniencia: segundos → minutos (redondeo hacia arriba si sobra)."""
    secs = remaining_seconds_for_user(*args)
    return (secs + 59) // 60
# app/models.py (al final del archivo)
import re
from sqlalchemy import event

_LANG_MAP = {
    "english": "en", "inglés": "en", "inglês": "en",
    "spanish": "es", "español": "es", "espanol": "es",
    "portuguese": "pt", "português": "pt", "portugues": "pt",
    "french": "fr", "francés": "fr", "français": "fr",
    "german": "de", "alemán": "de", "deutsch": "de",
    "italian": "it", "italiano": "it",
    "russian": "ru", "русский": "ru",
    "chinese": "zh", "mandarin": "zh", "中文": "zh",
    "japanese": "ja", "日本語": "ja",
    "korean": "ko", "한국어": "ko",
    "arabic": "ar", "عربي": "ar",
    "hindi": "hi", "dutch": "nl", "polish": "pl",
    "turkish": "tr", "ukrainian": "uk", "czech": "cs",
    "swedish": "sv", "romanian": "ro", "greek": "el",
    "hebrew": "he", "vietnamese": "vi", "indonesian": "id",
    "thai": "th", "bengali": "bn", "punjabi": "pa", "urdu": "ur",
    "filipino": "tl", "tagalog": "tl", "persian": "fa", "farsi": "fa",
    "catalan": "ca", "catalán": "ca", "català": "ca",
}

def _to_iso2(lang):
    if not lang:
        return None
    s = str(lang).strip().lower()
    if re.fullmatch(r"[a-z]{2}", s):
        return s
    return _LANG_MAP.get(s)

def _coerce_langs(target):
    for attr in ("language", "language_detected"):
        val = getattr(target, attr, None)
        if val is None:
            continue
        vv = _to_iso2(val)
        setattr(target, attr, vv if vv else None)

@event.listens_for(AudioJob, "before_insert", propagate=True)
def _aj_before_insert(mapper, connection, target):
    _coerce_langs(target)

@event.listens_for(AudioJob, "before_update", propagate=True)
def _aj_before_update(mapper, connection, target):
    _coerce_langs(target)
