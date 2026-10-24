"""Initial tables: users, refresh tokens, contacts, check-ins, SOS events.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

from app.models import UTCDateTime

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("display_name", sa.String(60)),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
    )
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("expires_at", UTCDateTime(), nullable=False),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table(
        "contacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.CheckConstraint("length(name) between 1 and 100", name="contacts_name_length"),
        sa.CheckConstraint("length(phone) between 3 and 30", name="contacts_phone_length"),
    )
    op.create_index("ix_contacts_user_id", "contacts", ["user_id"])

    op.create_table(
        "check_ins",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", UTCDateTime(), nullable=False),
        sa.Column("return_by", UTCDateTime(), nullable=False),
        sa.Column("time_zone", sa.String(64)),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("ended_at", UTCDateTime()),
        sa.Column("missed_at", UTCDateTime()),
        sa.Column("alerts_sent_at", UTCDateTime()),
        sa.Column("alerts_summary", sa.Text()),
        sa.Column("alerts_sent_count", sa.Integer()),
        sa.Column("confirmed_safe_at", UTCDateTime()),
        sa.Column("all_clear_sent_at", UTCDateTime()),
        sa.Column("all_clear_summary", sa.Text()),
        sa.CheckConstraint("status in ('active', 'safe', 'missed')", name="check_ins_status"),
    )
    op.create_index("ix_check_ins_user_id", "check_ins", ["user_id"])
    # Each person can only have one active check-in at a time.
    op.create_index(
        "check_ins_one_active_per_user",
        "check_ins",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    # Helps the every-minute checker find overdue check-ins quickly.
    op.create_index(
        "check_ins_active_return_by",
        "check_ins",
        ["return_by"],
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "sos_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("accuracy_meters", sa.Float()),
        sa.Column("alerts_sent_at", UTCDateTime()),
        sa.Column("alerts_summary", sa.Text()),
    )
    op.create_index("ix_sos_events_user_id", "sos_events", ["user_id"])
    op.create_index("ix_sos_events_created_at", "sos_events", ["created_at"])


def downgrade() -> None:
    for table in ("sos_events", "check_ins", "contacts", "refresh_tokens", "users"):
        op.drop_table(table)
