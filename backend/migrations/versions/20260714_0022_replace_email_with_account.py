"""Replace email login identity with a normalized account.

Revision ID: 20260714_0022
Revises: 20260714_0021
"""

from __future__ import annotations

import re

from alembic import op
import sqlalchemy as sa


revision = "20260714_0022"
down_revision = "20260714_0021"
branch_labels = None
depends_on = None


def _legacy_account(user_id: int, email: str, used: set[str]) -> str:
    local_part = (email or "").split("@", 1)[0].strip().lower()
    base = re.sub(r"[^a-z0-9_]+", "", local_part).strip("_")
    if len(base) < 4 or not base[0].isalnum():
        base = f"user{user_id}"
    base = base[:24]
    candidate = base
    if candidate in used:
        suffix = f"_{user_id}"
        candidate = f"{base[: 24 - len(suffix)]}{suffix}"
    counter = 2
    while candidate in used:
        suffix = f"_{user_id}_{counter}"
        candidate = f"{base[: 24 - len(suffix)]}{suffix}"
        counter += 1
    return candidate


def upgrade() -> None:
    op.add_column("users", sa.Column("account", sa.String(length=24), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, email FROM users ORDER BY id")).mappings()
    used: set[str] = set()
    for row in rows:
        account = _legacy_account(int(row["id"]), str(row["email"] or ""), used)
        used.add(account)
        connection.execute(
            sa.text("UPDATE users SET account = :account WHERE id = :user_id"),
            {"account": account, "user_id": row["id"]},
        )

    op.alter_column("users", "account", existing_type=sa.String(length=24), nullable=False)
    op.create_unique_constraint("uq_users_account", "users", ["account"])
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_column("users", "email")


def downgrade() -> None:
    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE users SET email = account || '-' || id || '@legacy.edunova.local'"
        )
    )
    op.alter_column("users", "email", existing_type=sa.String(length=255), nullable=False)
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.drop_constraint("uq_users_account", "users", type_="unique")
    op.drop_column("users", "account")
