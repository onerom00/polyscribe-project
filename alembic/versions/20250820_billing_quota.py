"""Billing fields, UsageLedger, PaymentEvent, AudioJob fields

Revision ID: 20250820_billing_quota
Revises: 8f2945600b71
Create Date: 2025-08-20 09:30:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# Revision identifiers, used by Alembic.
revision = "20250820_billing_quota"
down_revision = "8f2945600b71"
branch_labels = None
depends_on = None


def _has_table(inspector: Inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def _has_column(inspector: Inspector, table: str, column: str) -> bool:
    try:
        return any(c["name"] == column for c in inspector.get_columns(table))
    except Exception:
        return False


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # -----------------------------
    # USERS: agregar campos de billing/cuotas
    # -----------------------------
    if _has_table(insp, "users"):
        with op.batch_alter_table("users") as b:
            if not _has_column(insp, "users", "display_name"):
                b.add_column(sa.Column("display_name", sa.String(), nullable=True))

            if not _has_column(insp, "users", "plan_tier"):
                b.add_column(sa.Column("plan_tier", sa.String(), server_default="free", nullable=False))
            if not _has_column(insp, "users", "paypal_subscription_id"):
                b.add_column(sa.Column("paypal_subscription_id", sa.String(), nullable=True))
                b.create_index("ix_users_paypal_subscription_id", ["paypal_subscription_id"], unique=False)

            if not _has_column(insp, "users", "cycle_start"):
                b.add_column(sa.Column("cycle_start", sa.DateTime(), nullable=True))
            if not _has_column(insp, "users", "cycle_end"):
                b.add_column(sa.Column("cycle_end", sa.DateTime(), nullable=True))

            if not _has_column(insp, "users", "minute_quota"):
                b.add_column(sa.Column("minute_quota", sa.Integer(), server_default="0", nullable=False))
            if not _has_column(insp, "users", "minutes_used"):
                b.add_column(sa.Column("minutes_used", sa.Integer(), server_default="0", nullable=False))

            if not _has_column(insp, "users", "is_active"):
                b.add_column(sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False))

            # timestamps (si tu users no los tenía)
            if not _has_column(insp, "users", "created_at"):
                b.add_column(sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
            if not _has_column(insp, "users", "updated_at"):
                b.add_column(sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
    else:
        # Si faltara la tabla users (improbable en tu proyecto)
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email", sa.String(), unique=True, index=True),
            sa.Column("display_name", sa.String()),
            sa.Column("plan_tier", sa.String(), nullable=False, server_default="free"),
            sa.Column("paypal_subscription_id", sa.String(), index=True),
            sa.Column("cycle_start", sa.DateTime()),
            sa.Column("cycle_end", sa.DateTime()),
            sa.Column("minute_quota", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("minutes_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    # -----------------------------
    # AUDIO_JOBS: crear o ampliar columnas (status, idiomas, durations, resultados…)
    # -----------------------------
    jobstatus_enum = sa.Enum("queued", "processing", "done", "error", name="jobstatus")
    # En SQLite la Enum será TEXT con CHECK; en Postgres crea el tipo.

    if not _has_table(insp, "audio_jobs"):
        op.create_table(
            "audio_jobs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("original_filename", sa.String()),
            sa.Column("audio_s3_key", sa.String()),
            sa.Column("local_path", sa.String()),
            sa.Column("mime_type", sa.String()),
            sa.Column("size_bytes", sa.Integer()),
            sa.Column("status", jobstatus_enum, nullable=False, server_default="queued"),
            sa.Column("error_message", sa.Text()),
            sa.Column("language_forced", sa.String(8)),
            sa.Column("language_detected", sa.String(8)),
            sa.Column("duration_seconds", sa.Integer(), index=True),
            sa.Column("model_used", sa.String()),
            sa.Column("transcript", sa.Text()),
            sa.Column("summary_json", sa.JSON()),
            sa.Column("cost_cents", sa.Integer()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    else:
        with op.batch_alter_table("audio_jobs") as b:
            for col, typ, kwargs in [
                ("original_filename", sa.String(), dict(nullable=True)),
                ("audio_s3_key", sa.String(), dict(nullable=True)),
                ("local_path", sa.String(), dict(nullable=True)),
                ("mime_type", sa.String(), dict(nullable=True)),
                ("size_bytes", sa.Integer(), dict(nullable=True)),
                ("status", jobstatus_enum, dict(nullable=False, server_default="queued")),
                ("error_message", sa.Text(), dict(nullable=True)),
                ("language_forced", sa.String(8), dict(nullable=True)),
                ("language_detected", sa.String(8), dict(nullable=True)),
                ("duration_seconds", sa.Integer(), dict(nullable=True)),
                ("model_used", sa.String(), dict(nullable=True)),
                ("transcript", sa.Text(), dict(nullable=True)),
                ("summary_json", sa.JSON(), dict(nullable=True)),
                ("cost_cents", sa.Integer(), dict(nullable=True)),
                ("created_at", sa.DateTime(), dict(nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))),
                ("updated_at", sa.DateTime(), dict(nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))),
            ]:
                if not _has_column(insp, "audio_jobs", col):
                    b.add_column(sa.Column(col, typ, **kwargs))
            # índices útiles
            if "ix_audio_jobs_user_id" not in [ix["name"] for ix in insp.get_indexes("audio_jobs")]:
                b.create_index("ix_audio_jobs_user_id", ["user_id"], unique=False)
            if "ix_audio_jobs_duration_seconds" not in [ix["name"] for ix in insp.get_indexes("audio_jobs")]:
                b.create_index("ix_audio_jobs_duration_seconds", ["duration_seconds"], unique=False)

    # -----------------------------
    # USAGE_LEDGER: libro mayor de minutos
    # -----------------------------
    if not _has_table(insp, "usage_ledger"):
        op.create_table(
            "usage_ledger",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("job_id", sa.Integer(), sa.ForeignKey("audio_jobs.id", ondelete="SET NULL"), nullable=True),
            sa.Column("minutes_delta", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("reason", sa.String(32), nullable=False, server_default="job_charge"),
            sa.Column("note", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_usage_user_created", "usage_ledger", ["user_id", "created_at"], unique=False)

    # -----------------------------
    # PAYMENT_EVENTS: idempotencia de webhooks
    # -----------------------------
    if not _has_table(insp, "payment_events"):
        op.create_table(
            "payment_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("provider", sa.String(), nullable=False, server_default="paypal"),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("external_event_id", sa.String(), nullable=False),
            sa.Column("subscription_id", sa.String(), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("provider", "external_event_id", name="uq_payment_events_provider_event"),
        )
        op.create_index("ix_payment_sub_id_created", "payment_events", ["subscription_id", "created_at"], unique=False)


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Quitar tablas auxiliares
    if _has_table(insp, "payment_events"):
        op.drop_index("ix_payment_sub_id_created", table_name="payment_events")
        op.drop_table("payment_events")

    if _has_table(insp, "usage_ledger"):
        op.drop_index("ix_usage_user_created", table_name="usage_ledger")
        op.drop_table("usage_ledger")

    # audio_jobs: no borramos columnas una por una para evitar pérdida de datos;
    # en downgrade conservador podrías dejarlas, o si deseas, eliminarlas explícitamente.
    # Aquí ejemplo de eliminación segura de índices:
    if _has_table(insp, "audio_jobs"):
        idx_names = [ix["name"] for ix in insp.get_indexes("audio_jobs")]
        if "ix_audio_jobs_user_id" in idx_names:
            op.drop_index("ix_audio_jobs_user_id", table_name="audio_jobs")
        if "ix_audio_jobs_duration_seconds" in idx_names:
            op.drop_index("ix_audio_jobs_duration_seconds", table_name="audio_jobs")

    # users: tampoco eliminamos campos por seguridad (datos de billing).
    # Si necesitas limpiar, hazlo manualmente adaptando a tu entorno.
