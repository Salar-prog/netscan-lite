"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-08-31
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlmodel import SQLModel

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create groups table
    op.create_table(
        "groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("miss_threshold", sa.Integer(), nullable=False),
        sa.Column("quarantine_hours", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_groups_name"), "groups", ["name"], unique=True)

    # Create ip_addresses table
    op.create_table(
        "ip_addresses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("ip", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("hostname", sa.String(), nullable=True),
        sa.Column("mac_address", sa.String(), nullable=True),
        sa.Column("mac_vendor", sa.String(), nullable=True),
        sa.Column("open_ports", sa.JSON(), nullable=True),
        sa.Column("discovery_method", sa.String(), nullable=True),
        sa.Column("consecutive_misses", sa.Integer(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ip", "group_id", name="uq_ip_group"),
    )
    op.create_index(op.f("ix_ip_addresses_group_id"), "ip_addresses", ["group_id"], unique=False)
    op.create_index(op.f("ix_ip_addresses_ip"), "ip_addresses", ["ip"], unique=False)
    op.create_index(op.f("ix_ip_addresses_status"), "ip_addresses", ["status"], unique=False)
    op.create_index(op.f("ix_ip_addresses_hostname"), "ip_addresses", ["hostname"], unique=False)
    op.create_index(op.f("ix_ip_addresses_mac_address"), "ip_addresses", ["mac_address"], unique=False)


def downgrade() -> None:
    op.drop_table("ip_addresses")
    op.drop_table("groups")
