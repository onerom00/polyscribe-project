# app/models.py
from __future__ import annotations

import datetime as dt

from app import db  # usa la instancia global creada en app/__init__.py


def utcnow():
    return dt.datetime.utcnow()


# ---------------------------------------------------------
# MODELO DE USUARIOS (para login simple y admin)
# ---------------------------------------------------------
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)

    # Opcional: contraseña hash si más adelante quieres login real
    password_hash = db.Column(db.String(255), nullable=True)

    is_admin = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"


# ---------------------------------------------------------
# JOBS DE TRANSCRIPCIÓN
# ---------------------------------------------------------
class AudioJob(db.Model):
    __tablename__ = "audio_jobs"

    # CLAVE PRIMARIA AUTOINCREMENT
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # quién (puede ser id interno o email hash; lo usamos como string flexible)
    user_id = db.Column(db.String(255), nullable=True, index=True)

    # archivo
    filename = db.Column(db.String(255), nullable=True)          # nombre lógico visible
    original_filename = db.Column(db.String(255), nullable=True) # nombre original
    audio_s3_key = db.Column(db.String(512), nullable=True, default="")
    local_path = db.Column(db.String(1024), nullable=True)
    mime_type = db.Column(db.String(120), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=True)

    # idiomas y estado
    language = db.Column(db.String(10), nullable=True, default="auto")
    language_forced = db.Column(db.Boolean, nullable=False, default=False)
    language_detected = db.Column(db.String(10), nullable=True)

    status = db.Column(db.String(32), nullable=True, default="done")
    error = db.Column(db.Integer, nullable=False, default=0)
    error_message = db.Column(db.Text, nullable=True)

    # contenidos
    transcript = db.Column(db.Text, nullable=True)
    summary = db.Column(db.Text, nullable=True)

    # métricas / costos (opcionales)
    duration_seconds = db.Column(db.Float, nullable=True)
    model_used = db.Column(db.String(64), nullable=True)
    cost_cents = db.Column(db.Integer, nullable=True)

    # timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    def __repr__(self) -> str:
        return f"<AudioJob id={self.id} user={self.user_id} status={self.status}>"


# ---------------------------------------------------------
# USO DE MINUTOS (FREE + PLANES DE PAGO)
# ---------------------------------------------------------
class UsageLedger(db.Model):
    """
    Tabla agregada por usuario:
    - minutes_total: minutos totales asignados (free + pagos)
    - minutes_used:  minutos ya consumidos
    """

    __tablename__ = "usage_ledger"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(255), nullable=False, index=True)

    minutes_total = db.Column(db.Integer, nullable=False, default=0)
    minutes_used = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    @property
    def minutes_left(self) -> int:
        return max(self.minutes_total - self.minutes_used, 0)

    def add_minutes(self, amount: int, reason: str = "", source: str = "", meta=None):
        """Crédito de minutos (p.ej. plan Starter, bonus, etc.)."""
        if amount <= 0:
            return
        self.minutes_total += amount
        event = UsageLedgerEvent(
            user_id=self.user_id,
            delta_minutes=amount,
            reason=reason or "credit",
            source=source or "system",
            meta=meta or {},
        )
        db.session.add(event)

    def consume_minutes(self, amount: int, reason: str = "", source: str = "", meta=None):
        """Descuento de minutos (p.ej. nueva transcripción)."""
        if amount <= 0:
            return
        self.minutes_used += amount
        event = UsageLedgerEvent(
            user_id=self.user_id,
            delta_minutes=-amount,
            reason=reason or "debit",
            source=source or "usage",
            meta=meta or {},
        )
        db.session.add(event)

    def __repr__(self) -> str:
        return (
            f"<UsageLedger user_id={self.user_id} "
            f"total={self.minutes_total} used={self.minutes_used}>"
        )


# ---------------------------------------------------------
# HISTORIAL DE MOVIMIENTOS DE MINUTOS
# ---------------------------------------------------------
class UsageLedgerEvent(db.Model):
    __tablename__ = "usage_ledger_events"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(255), nullable=False, index=True)

    # positivo = crédito, negativo = consumo
    delta_minutes = db.Column(db.Integer, nullable=False)

    reason = db.Column(db.String(64), nullable=True)   # "free_tier", "starter_plan", etc.
    source = db.Column(db.String(64), nullable=True)   # "system", "webhook", "usage", ...

    meta = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def __repr__(self) -> str:
        return (
            f"<UsageLedgerEvent user_id={self.user_id} "
            f"delta={self.delta_minutes} reason={self.reason}>"
        )
