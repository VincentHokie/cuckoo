"""vm_import table (for Cuckoo project)

Revision ID: bb1024e614b7
Revises: cb1024e614b7
Create Date: 2017-02-07 00:29:30.030173

"""

# Revision identifiers, used by Alembic.
revision = "bb1024e614b7"
down_revision = "cb1024e614b7"

import datetime

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        "submit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vm_name", sa.String(length=64), nullable=False),
        sa.Column("vm_file", sa.String(length=64), nullable=False),
        sa.Column("os", sa.String(length=64), nullable=False),
        sa.Column("os_version", sa.String(length=64), nullable=False),
        sa.Column("os_arch", sa.String(length=64), nullable=False),
        sa.Column("cpu", sa.Integer(), nullable=False),
        sa.Column("ram", sa.Integer(), nullable=False),
        sa.Column("file_log", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column(
            "picked_up", sa.Boolean, nullable=False, default=False
        ),
        sa.Column(
            "added_on", sa.DateTime(timezone=False),
            default=datetime.datetime.now, nullable=False
        ),
        sa.PrimaryKeyConstraint("id")
    )

def downgrade():
    pass
