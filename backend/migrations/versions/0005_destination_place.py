"""Destination picked from the address search: longer text and its map position.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("check_ins") as batch:
        batch.alter_column(
            "destination", type_=sa.String(255), existing_type=sa.String(120), existing_nullable=True
        )
        batch.add_column(sa.Column("destination_latitude", sa.Float(), nullable=True))
        batch.add_column(sa.Column("destination_longitude", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("check_ins") as batch:
        batch.drop_column("destination_longitude")
        batch.drop_column("destination_latitude")
        batch.alter_column(
            "destination", type_=sa.String(120), existing_type=sa.String(255), existing_nullable=True
        )
