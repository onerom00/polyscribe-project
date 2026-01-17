"""usage_ledger_events table

Revision ID: 20250820_usage_events
Revises: 20250820_billing_quota
Create Date: 2025-08-20 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "20250820_usage_events"
down_revision = "20250820_billing_quota"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "usage_ledger_events" not in insp.get_table_names():
        op.create_table(
            "usage_ledger_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("job_id", sa.Integer(), sa.ForeignKey("audio_jobs.id", ondelete="SET NULL"), nullable=True),
            sa.Column("minutes_delta", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("reason", sa.String(32), nullable=False, server_default="job_charge"),
            sa.Column("note", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_usage_events_user_created", "usage_ledger_events", ["user_id", "created_at"], unique=False)

def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "usage_ledger_events" in insp.get_table_names():
        op.drop_index("ix_usage_events_user_created", table_name="usage_ledger_events")
        op.drop_table("usage_ledger_events")