"""initial migration
Revision ID: 0001_initial
Revises: 
Create Date: 2025-08-05 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=True)
    )
    op.create_table('subscriptions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('plan', sa.Enum('free', 'basic', name='plan_enum'), nullable=False),
        sa.Column('status', sa.Enum('active', 'canceled', name='subscription_status_enum'), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('ends_at', sa.DateTime(), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(length=255), nullable=False)
    )
    op.create_table('audio_jobs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('filename', sa.String(length=512), nullable=False),
        sa.Column('upload_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.Enum('queued', 'done', 'error', name='job_status_enum'), nullable=False),
        sa.Column('duration_sec', sa.Numeric(), nullable=True),
        sa.Column('error_msg', sa.Text(), nullable=True)
    )
    op.create_table('transcriptions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('audio_jobs.id'), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )
    op.create_table('summaries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('transcription_id', sa.Integer(), sa.ForeignKey('transcriptions.id'), nullable=False),
        sa.Column('lang', sa.String(length=2), nullable=False),
        sa.Column('text', sa.Text(), nullable=False)
    )
    op.create_table('usage_ledger',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('audio_jobs.id'), nullable=False),
        sa.Column('minutes_used', sa.Numeric(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(), nullable=False)
    )
    op.create_table('payments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('stripe_payment_id', sa.String(length=255), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('paid_at', sa.DateTime(), nullable=False)
    )

def downgrade():
    op.drop_table('payments')
    op.drop_table('usage_ledger')
    op.drop_table('summaries')
    op.drop_table('transcriptions')
    op.drop_table('audio_jobs')
    op.drop_table('subscriptions')
    op.drop_table('users')
    sa.Enum(name='job_status_enum').drop(op.get_bind(), 'job_status_enum')
    sa.Enum(name='subscription_status_enum').drop(op.get_bind(), 'subscription_status_enum')
    sa.Enum(name='plan_enum').drop(op.get_bind(), 'plan_enum')
