"""نسخهٔ فروش: جدول مشتری‌ها (tenants)، درخواست پلن، و اتصال کاربر به مستأجر.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-12
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False, server_default="free"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("owner_user_id", sa.String(36), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("suspended_reason", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)
    op.create_index("ix_tenants_plan", "tenants", ["plan"])
    op.create_index("ix_tenants_status", "tenants", ["status"])
    op.create_index("ix_tenants_owner_user_id", "tenants", ["owner_user_id"])

    op.create_table(
        "plan_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False),
        sa.Column("months", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("amount_toman", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("reference", sa.String(120), nullable=False, server_default=""),
        sa.Column("decided_by", sa.String(36), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_plan_requests_tenant_id", "plan_requests", ["tenant_id"])
    op.create_index("ix_plan_requests_status", "plan_requests", ["status"])

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("tenant_id", sa.String(36), nullable=True))
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    # --- backfill: هر کاربر بدون مستأجر یک مستأجر اختصاصی می‌گیرد (بدون حذف داده) ---
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, email, name FROM users WHERE tenant_id IS NULL")).fetchall()
    now = datetime.now(timezone.utc)
    for uid, email, name in rows:
        tid = str(uuid.uuid4())
        label = (name or (email or "user").split("@")[0])[:160]
        bind.execute(sa.text(
            "INSERT INTO tenants (id, name, slug, plan, status, owner_user_id, settings, notes, "
            "suspended_reason, created_at, updated_at) VALUES (:id, :name, :slug, 'business', 'active', "
            ":owner, '{}', 'مهاجرت خودکار از نصب تک‌کاربره', '', :now, :now)"),
            {"id": tid, "name": label, "slug": f"legacy-{tid[:8]}", "owner": uid, "now": now})
        bind.execute(sa.text("UPDATE users SET tenant_id = :tid WHERE id = :uid"), {"tid": tid, "uid": uid})


def downgrade() -> None:
    op.drop_index("ix_users_tenant_id", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("tenant_id")
    op.drop_index("ix_plan_requests_status", table_name="plan_requests")
    op.drop_index("ix_plan_requests_tenant_id", table_name="plan_requests")
    op.drop_table("plan_requests")
    for ix in ("ix_tenants_owner_user_id", "ix_tenants_status", "ix_tenants_plan", "ix_tenants_slug"):
        op.drop_index(ix, table_name="tenants")
    op.drop_table("tenants")
