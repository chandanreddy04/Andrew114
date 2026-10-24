"""SOS stays active until "I'm safe": battery, details link, all-clear.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

from app.models import UTCDateTime

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sos_events", sa.Column("battery_level", sa.Integer()))
    op.add_column("sos_events", sa.Column("share_token", sa.String(64)))
    op.add_column("sos_events", sa.Column("ended_at", UTCDateTime()))
    op.add_column("sos_events", sa.Column("all_clear_summary", sa.Text()))
    op.create_index("ix_sos_events_share_token", "sos_events", ["share_token"], unique=True)
    # Older SOS alerts count as already over.
    op.execute("update sos_events set ended_at = created_at")


def downgrade() -> None:
    op.drop_index("ix_sos_events_share_token", "sos_events")
    for column in ("all_clear_summary", "ended_at", "share_token", "battery_level"):
        op.drop_column("sos_events", column)
