"""Session details: destination, location sharing, outfit photo, 7-day deletion.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

from app.models import UTCDateTime

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("check_ins", sa.Column("destination", sa.String(120)))
    op.add_column(
        "check_ins",
        sa.Column("share_location", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("check_ins", sa.Column("latitude", sa.Float()))
    op.add_column("check_ins", sa.Column("longitude", sa.Float()))
    op.add_column("check_ins", sa.Column("accuracy_meters", sa.Float()))
    op.add_column("check_ins", sa.Column("location_at", UTCDateTime()))
    op.add_column("check_ins", sa.Column("share_token", sa.String(64)))
    op.add_column("check_ins", sa.Column("delete_after", UTCDateTime()))
    op.create_index("ix_check_ins_share_token", "check_ins", ["share_token"], unique=True)
    op.create_index("ix_check_ins_delete_after", "check_ins", ["delete_after"])

    # Sessions that already ended get the same 7 days from now.
    op.execute(
        "update check_ins set delete_after = current_timestamp + interval '7 days' "
        "where status <> 'active'"
        if op.get_bind().dialect.name == "postgresql"
        else "update check_ins set delete_after = datetime('now', '+7 days') "
        "where status <> 'active'"
    )

    op.create_table(
        "session_photos",
        sa.Column(
            "check_in_id",
            sa.Uuid(),
            sa.ForeignKey("check_ins.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("content_type", sa.String(30), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("session_photos")
    op.drop_index("ix_check_ins_delete_after", "check_ins")
    op.drop_index("ix_check_ins_share_token", "check_ins")
    for column in (
        "delete_after",
        "share_token",
        "location_at",
        "accuracy_meters",
        "longitude",
        "latitude",
        "share_location",
        "destination",
    ):
        op.drop_column("check_ins", column)
